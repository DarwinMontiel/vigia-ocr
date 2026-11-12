"""Bot real: Chrome + Selenium contra el portal ficticio servido por uvicorn (``pytest -m e2e``).

Requiere Chrome (o Chromium) y los motores de ``.[ocr]``. Recorre el catálogo completo de
Puerto Candela y compara lo guardado con la verdad del catálogo.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import httpx
import pytest
import uvicorn

from tests.conftest import RelojFalso
from vigia_ocr.adaptadores.ocr import crear_motores
from vigia_ocr.adaptadores.persistencia.sql import RepositorioSQL, crear_esquema, crear_motor_bd
from vigia_ocr.adaptadores.portal.selenium_portal import PortalSelenium
from vigia_ocr.adaptadores.preprocesado import VARIANTES_POR_DEFECTO
from vigia_ocr.adaptadores.reloj import RelojSistema
from vigia_ocr.aplicacion.circuit_breaker import CircuitBreaker
from vigia_ocr.aplicacion.consultar import ServicioConsulta
from vigia_ocr.aplicacion.lector import LectorConsenso
from vigia_ocr.dominio.errores import MotorNoDisponible
from vigia_ocr.dominio.modelos import Desenlace, Radicado
from vigia_ocr.portal_ficticio import catalogo
from vigia_ocr.portal_ficticio.app import crear_app

pytestmark = pytest.mark.e2e
CORTE = date(2026, 11, 12)


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def portal_url() -> Iterator[str]:
    puerto = puerto_libre()
    servidor = uvicorn.Server(
        uvicorn.Config(crear_app(semilla=2026), host="127.0.0.1", port=puerto, log_level="warning")
    )
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    url = f"http://127.0.0.1:{puerto}"
    for _ in range(50):
        try:
            if httpx.get(f"{url}/salud").status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.1)
    yield url
    servidor.should_exit = True
    hilo.join(timeout=5)


@pytest.fixture(scope="module")
def navegador(portal_url: str) -> Iterator[PortalSelenium]:
    with PortalSelenium(
        portal_url,
        headless=os.environ.get("VIGIA_NAVEGADOR_HEADLESS", "true") != "false",
        binario=os.environ.get("VIGIA_NAVEGADOR_BINARIO"),
        chromedriver=os.environ.get("VIGIA_CHROMEDRIVER"),
    ) as portal:
        yield portal


@pytest.fixture(scope="module")
def lector() -> LectorConsenso:
    try:
        motores = crear_motores(["ddddocr", "tesseract"], omitir_no_disponibles=True)
    except MotorNoDisponible as error:
        pytest.skip(str(error))
    return LectorConsenso.desde_motores(motores, VARIANTES_POR_DEFECTO)


def test_el_bot_recorta_la_imagen_tal_como_la_sirve_el_portal(navegador: PortalSelenium) -> None:
    imagen = navegador.obtener_imagen_estado(Radicado(catalogo.EXPEDIENTES[0].radicado))
    assert imagen.size == (240, 72)
    assert imagen.mode == "RGB"


def test_lote_completo_contra_el_portal(
    navegador: PortalSelenium, lector: LectorConsenso, tmp_path: Path
) -> None:
    motor_bd = crear_motor_bd(f"sqlite:///{tmp_path / 'e2e.db'}")
    crear_esquema(motor_bd)
    repositorio = RepositorioSQL(motor_bd)
    reloj = RelojSistema()
    servicio = ServicioConsulta(
        navegador, lector, repositorio, CircuitBreaker(reloj), reloj, max_imagenes=5
    )
    radicados = [Radicado(e.radicado) for e in catalogo.EXPEDIENTES]
    radicados.append(Radicado("PCA-2026-00999"))

    resumen = servicio.procesar_lote(radicados, CORTE)

    por_radicado = {r.radicado.valor: r for r in resumen.resultados}
    assert por_radicado["PCA-2026-00999"].desenlace is Desenlace.RADICADO_INEXISTENTE
    guardados = [r for r in resumen.resultados if r.desenlace is Desenlace.GUARDADO]
    equivocados = [
        r.radicado.valor
        for r in guardados
        if r.resultado and r.resultado.codigo != catalogo.POR_RADICADO[r.radicado.valor].codigo
    ]
    assert equivocados == []
    assert len(guardados) >= 11  # de 12; el resto queda pendiente, nunca equivocado

    segunda = servicio.procesar_lote(radicados[:3], CORTE)
    assert all(r.desenlace is Desenlace.OMITIDO_YA_EXISTIA for r in segunda.resultados)


def test_portal_caido_abre_el_circuito(
    navegador: PortalSelenium, lector: LectorConsenso, portal_url: str
) -> None:
    from vigia_ocr.adaptadores.persistencia.memoria import RepositorioEnMemoria

    reloj = RelojFalso()
    servicio = ServicioConsulta(
        navegador,
        lector,
        RepositorioEnMemoria(),
        CircuitBreaker(reloj, umbral_fallos=2, enfriamiento_s=60),
        reloj,
    )
    httpx.post(f"{portal_url}/_simulacion/caida", params={"activa": True})
    try:
        resumen = servicio.procesar_lote(
            [Radicado(e.radicado) for e in catalogo.EXPEDIENTES[:4]], CORTE
        )
    finally:
        httpx.post(f"{portal_url}/_simulacion/caida", params={"activa": False})
    assert [r.desenlace for r in resumen.resultados] == [
        Desenlace.PORTAL_NO_DISPONIBLE,
        Desenlace.PORTAL_NO_DISPONIBLE,
        Desenlace.CIRCUITO_ABIERTO,
        Desenlace.CIRCUITO_ABIERTO,
    ]
