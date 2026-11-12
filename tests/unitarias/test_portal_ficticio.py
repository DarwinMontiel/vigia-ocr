from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from vigia_ocr.portal_ficticio import catalogo
from vigia_ocr.portal_ficticio.app import crear_app

RADICADO = catalogo.EXPEDIENTES[0].radicado


@pytest.fixture
def cliente() -> TestClient:
    return TestClient(crear_app(semilla=7))


def test_inicio_tiene_el_formulario_que_usa_el_bot(cliente: TestClient) -> None:
    html = cliente.get("/").text
    assert 'id="radicado"' in html
    assert 'id="boton-consultar"' in html
    assert "ficticio" in html.lower()


def test_consulta_muestra_ficha_con_imagen_y_nombre_enmascarado(cliente: TestClient) -> None:
    respuesta = cliente.get("/consulta", params={"radicado": RADICADO.lower()})
    assert respuesta.status_code == 200
    assert 'id="imagen-estado"' in respuesta.text
    assert "Eustaquio B*** F***" in respuesta.text
    assert catalogo.EXPEDIENTES[0].codigo not in respuesta.text  # el código solo va en la imagen


def test_radicado_inexistente(cliente: TestClient) -> None:
    respuesta = cliente.get("/consulta", params={"radicado": "PCA-2026-99999"})
    assert respuesta.status_code == 404
    assert 'id="mensaje-error"' in respuesta.text
    assert cliente.get("/imagen-estado", params={"radicado": "X"}).status_code == 404


def test_cada_solicitud_de_imagen_trae_ruido_nuevo(cliente: TestClient) -> None:
    primera = cliente.get("/imagen-estado", params={"radicado": RADICADO})
    segunda = cliente.get("/imagen-estado", params={"radicado": RADICADO})
    assert primera.headers["content-type"] == "image/png"
    assert primera.headers["cache-control"] == "no-store"
    assert primera.content != segunda.content
    with Image.open(io.BytesIO(primera.content)) as imagen:
        assert imagen.size == (240, 72)


def test_simulacion_de_caida_y_recuperacion(cliente: TestClient) -> None:
    assert cliente.post("/_simulacion/caida", params={"activa": True}).json() == {"caido": True}
    caido = cliente.get("/")
    assert caido.status_code == 503
    assert 'id="fuera-de-servicio"' in caido.text
    assert cliente.get("/salud").status_code == 200  # la salud no se ve afectada
    cliente.post("/_simulacion/caida", params={"activa": False})
    assert cliente.get("/").status_code == 200


def test_tasa_de_fallos_aleatoria_reproducible() -> None:
    cliente = TestClient(crear_app(semilla=1, tasa_fallos=0.5))
    codigos = [cliente.get("/").status_code for _ in range(40)]
    assert 10 < codigos.count(503) < 30


def test_salud(cliente: TestClient) -> None:
    assert cliente.get("/salud").json() == {"estado": "ok", "expedientes": 12}


def test_catalogo_es_coherente() -> None:
    radicados = [e.radicado for e in catalogo.EXPEDIENTES]
    assert len(radicados) == len(set(radicados))
    assert all(e.documento.startswith("99.999.") for e in catalogo.EXPEDIENTES)
    assert len({e.estado for e in catalogo.EXPEDIENTES}) == 5
