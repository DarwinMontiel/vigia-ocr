"""Caso de uso completo con dobles: idempotencia, reintento de imagen, breaker y verificación."""

from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import (
    FECHA_CORTE,
    MotorQueLeeMetadatos,
    PortalGuion,
    RelojFalso,
    VarianteIdentidad,
    codigo_ejemplo,
)
from vigia_ocr.adaptadores.persistencia.memoria import RepositorioEnMemoria
from vigia_ocr.aplicacion.circuit_breaker import CircuitBreaker
from vigia_ocr.aplicacion.consultar import ServicioConsulta
from vigia_ocr.aplicacion.lector import LectorConsenso
from vigia_ocr.dominio.codigo import EstadoObligacion
from vigia_ocr.dominio.errores import ErrorVerificacion, PortalNoDisponible
from vigia_ocr.dominio.modelos import Desenlace, Radicado, ResultadoConsulta

BUENO = codigo_ejemplo("48213")
EMBARGO = codigo_ejemplo("10974", EstadoObligacion.EMBARGO)


def crear_servicio(
    portal: PortalGuion,
    reloj: RelojFalso,
    repositorio: RepositorioEnMemoria | None = None,
    *,
    max_imagenes: int = 3,
    umbral: int = 2,
    confianza_minima: float = 0.0,
) -> tuple[ServicioConsulta, RepositorioEnMemoria]:
    repo = repositorio or RepositorioEnMemoria()
    lector = LectorConsenso.desde_motores(
        [MotorQueLeeMetadatos("a"), MotorQueLeeMetadatos("b")], [VarianteIdentidad()]
    )
    servicio = ServicioConsulta(
        portal,
        lector,
        repo,
        CircuitBreaker(reloj, umbral_fallos=umbral, enfriamiento_s=60),
        reloj,
        max_imagenes=max_imagenes,
        confianza_minima=confianza_minima,
    )
    return servicio, repo


def test_guarda_y_verifica_el_estado_leido(reloj: RelojFalso, radicados: list[Radicado]) -> None:
    portal = PortalGuion({radicados[0].valor: [BUENO]})
    servicio, repo = crear_servicio(portal, reloj)

    resultado = servicio.procesar(radicados[0], FECHA_CORTE)

    assert resultado.desenlace is Desenlace.GUARDADO
    assert resultado.resultado is not None
    assert resultado.resultado.estado is EstadoObligacion.ACUERDO_DE_PAGO
    guardado = repo.obtener(radicados[0], FECHA_CORTE)
    assert guardado is not None
    assert guardado.codigo == BUENO
    assert guardado.imagenes_consultadas == 1
    assert guardado.consultado_en == reloj.ahora()


def test_idempotencia_no_vuelve_a_consultar_el_portal(
    reloj: RelojFalso, radicados: list[Radicado]
) -> None:
    portal = PortalGuion({radicados[0].valor: [BUENO]})
    servicio, _ = crear_servicio(portal, reloj)

    servicio.procesar(radicados[0], FECHA_CORTE)
    segunda = servicio.procesar(radicados[0], FECHA_CORTE)

    assert segunda.desenlace is Desenlace.OMITIDO_YA_EXISTIA
    assert portal.llamadas == [radicados[0].valor]


def test_otra_fecha_de_corte_si_se_consulta(reloj: RelojFalso, radicados: list[Radicado]) -> None:
    portal = PortalGuion({radicados[0].valor: [BUENO]})
    servicio, _ = crear_servicio(portal, reloj)
    servicio.procesar(radicados[0], FECHA_CORTE)
    otra = servicio.procesar(radicados[0], date(2026, 11, 13))
    assert otra.desenlace is Desenlace.GUARDADO
    assert len(portal.llamadas) == 2


def test_pide_otra_imagen_si_la_lectura_no_es_confiable(
    reloj: RelojFalso, radicados: list[Radicado]
) -> None:
    portal = PortalGuion({radicados[0].valor: ["ruido", "AP48?", BUENO]})
    servicio, repo = crear_servicio(portal, reloj)

    resultado = servicio.procesar(radicados[0], FECHA_CORTE)

    assert resultado.desenlace is Desenlace.GUARDADO
    assert len(portal.llamadas) == 3
    guardado = repo.obtener(radicados[0], FECHA_CORTE)
    assert guardado is not None
    assert guardado.imagenes_consultadas == 3


def test_sin_consenso_tras_el_maximo_de_imagenes(
    reloj: RelojFalso, radicados: list[Radicado]
) -> None:
    portal = PortalGuion({radicados[0].valor: ["ruido"]})
    servicio, repo = crear_servicio(portal, reloj, max_imagenes=2)

    resultado = servicio.procesar(radicados[0], FECHA_CORTE)

    assert resultado.desenlace is Desenlace.SIN_LECTURA_CONFIABLE
    assert "2 imágenes" in resultado.detalle
    assert repo.obtener(radicados[0], FECHA_CORTE) is None


def test_confianza_minima_rechaza_lecturas_debiles(
    reloj: RelojFalso, radicados: list[Radicado]
) -> None:
    portal = PortalGuion({radicados[0].valor: [BUENO]})
    servicio, _ = crear_servicio(portal, reloj, confianza_minima=1.01, max_imagenes=1)
    assert servicio.procesar(radicados[0], FECHA_CORTE).desenlace is (
        Desenlace.SIN_LECTURA_CONFIABLE
    )


def test_radicado_inexistente_es_error_de_negocio(
    reloj: RelojFalso, radicados: list[Radicado]
) -> None:
    servicio, _ = crear_servicio(PortalGuion({}), reloj)
    resultado = servicio.procesar(radicados[0], FECHA_CORTE)
    assert resultado.desenlace is Desenlace.RADICADO_INEXISTENTE
    assert "No existe" in resultado.detalle


def test_portal_caido_abre_el_circuito_y_protege_el_resto_del_lote(
    reloj: RelojFalso, radicados: list[Radicado]
) -> None:
    portal = PortalGuion({r.valor: [BUENO] for r in radicados}, caido=True)
    servicio, _ = crear_servicio(portal, reloj, umbral=2)

    resumen = servicio.procesar_lote(radicados, FECHA_CORTE)

    assert [r.desenlace for r in resumen.resultados] == [
        Desenlace.PORTAL_NO_DISPONIBLE,
        Desenlace.PORTAL_NO_DISPONIBLE,
        Desenlace.CIRCUITO_ABIERTO,
    ]
    assert len(portal.llamadas) == 2  # el tercero ni siquiera tocó el portal
    assert resumen.pendientes == radicados
    assert resumen.exitosos == 0


def test_el_lote_se_recupera_cuando_el_portal_vuelve(
    reloj: RelojFalso, radicados: list[Radicado]
) -> None:
    portal = PortalGuion({r.valor: [BUENO] for r in radicados}, caido=True)
    servicio, _ = crear_servicio(portal, reloj, umbral=1)
    servicio.procesar(radicados[0], FECHA_CORTE)

    portal.caido = False
    reloj.avanzar(61)
    resumen = servicio.procesar_lote(radicados, FECHA_CORTE)

    assert resumen.exitosos == 3
    assert resumen.pendientes == []


def test_falla_transitoria_en_una_imagen_posterior(
    reloj: RelojFalso, radicados: list[Radicado]
) -> None:
    portal = PortalGuion({radicados[0].valor: ["ruido", PortalNoDisponible("timeout")]})
    servicio, _ = crear_servicio(portal, reloj)
    resultado = servicio.procesar(radicados[0], FECHA_CORTE)
    assert resultado.desenlace is Desenlace.PORTAL_NO_DISPONIBLE


def test_resumen_del_lote(reloj: RelojFalso, radicados: list[Radicado]) -> None:
    portal = PortalGuion({radicados[0].valor: [BUENO], radicados[1].valor: [EMBARGO]})
    servicio, _ = crear_servicio(portal, reloj)

    resumen = servicio.procesar_lote(radicados, FECHA_CORTE)

    assert resumen.total == 3
    assert resumen.contar(Desenlace.GUARDADO) == 2
    assert resumen.contar(Desenlace.RADICADO_INEXISTENTE) == 1
    assert resumen.pendientes == []  # inexistente no se reintenta: es de negocio


class RepositorioQueMiente(RepositorioEnMemoria):
    """Simula una escritura que no quedó como se pidió (trigger, truncamiento, réplica...)."""

    def guardar(self, resultado: ResultadoConsulta) -> bool:
        from dataclasses import replace

        return super().guardar(replace(resultado, codigo=EMBARGO, estado=EstadoObligacion.EMBARGO))


class RepositorioQuePierde(RepositorioEnMemoria):
    def guardar(self, resultado: ResultadoConsulta) -> bool:
        return True


def test_verificacion_tras_guardar_detecta_datos_distintos(
    reloj: RelojFalso, radicados: list[Radicado]
) -> None:
    portal = PortalGuion({radicados[0].valor: [BUENO]})
    servicio, _ = crear_servicio(portal, reloj, RepositorioQueMiente())
    with pytest.raises(ErrorVerificacion, match="se guardó"):
        servicio.procesar(radicados[0], FECHA_CORTE)


def test_verificacion_tras_guardar_detecta_registro_perdido(
    reloj: RelojFalso, radicados: list[Radicado]
) -> None:
    portal = PortalGuion({radicados[0].valor: [BUENO]})
    servicio, _ = crear_servicio(portal, reloj, RepositorioQuePierde())
    with pytest.raises(ErrorVerificacion, match="no aparece"):
        servicio.procesar(radicados[0], FECHA_CORTE)


class RepositorioConCarrera(RepositorioEnMemoria):
    """Otro bot guarda el mismo radicado entre nuestra consulta y nuestro INSERT."""

    def __init__(self, ganador: ResultadoConsulta) -> None:
        super().__init__()
        self._ganador = ganador
        self._primera = True

    def obtener(self, radicado: Radicado, fecha_corte: date) -> ResultadoConsulta | None:
        if self._primera:
            self._primera = False
            return None
        return super().obtener(radicado, fecha_corte)

    def guardar(self, resultado: ResultadoConsulta) -> bool:
        super().guardar(self._ganador)
        return super().guardar(resultado)


def test_carrera_entre_bots_gana_el_primero(reloj: RelojFalso, radicados: list[Radicado]) -> None:
    portal = PortalGuion({radicados[0].valor: [BUENO]})
    referencia, _ = crear_servicio(PortalGuion({radicados[0].valor: [BUENO]}), reloj)
    ganador = referencia.procesar(radicados[0], FECHA_CORTE).resultado
    assert ganador is not None
    servicio, _ = crear_servicio(portal, reloj, RepositorioConCarrera(ganador))

    resultado = servicio.procesar(radicados[0], FECHA_CORTE)

    assert resultado.desenlace is Desenlace.OMITIDO_YA_EXISTIA


def test_max_imagenes_invalido(reloj: RelojFalso) -> None:
    with pytest.raises(ValueError, match="max_imagenes"):
        crear_servicio(PortalGuion(), reloj, max_imagenes=0)
