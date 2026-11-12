from __future__ import annotations

import io

import pytest
from PIL import Image

from vigia_ocr.adaptadores.portal.recorte import Caja, recortar


def captura_con_rectangulo(ancho: int, alto: int, caja: tuple[int, int, int, int]) -> bytes:
    imagen = Image.new("RGB", (ancho, alto), "white")
    imagen.paste((200, 0, 0), caja)
    bufer = io.BytesIO()
    imagen.save(bufer, format="PNG")
    return bufer.getvalue()


def test_recorta_exactamente_la_caja() -> None:
    captura = captura_con_rectangulo(400, 300, (100, 50, 340, 122))
    recorte = recortar(captura, Caja(100, 50, 240, 72))
    assert recorte.size == (240, 72)
    assert recorte.getpixel((0, 0)) == (200, 0, 0)
    assert recorte.getpixel((239, 71)) == (200, 0, 0)


def test_con_escala_hidpi_devuelve_el_tamano_css() -> None:
    captura = captura_con_rectangulo(800, 600, (200, 100, 680, 244))  # todo ×2
    recorte = recortar(captura, Caja(100, 50, 240, 72), escala=2.0)
    assert recorte.size == (240, 72)
    assert recorte.getpixel((120, 36)) == (200, 0, 0)


def test_caja_fuera_de_la_captura() -> None:
    captura = captura_con_rectangulo(200, 100, (0, 0, 10, 10))
    with pytest.raises(ValueError, match="fuera de la captura"):
        recortar(captura, Caja(150, 50, 240, 72))


def test_caja_vacia_significa_imagen_sin_cargar() -> None:
    captura = captura_con_rectangulo(200, 100, (0, 0, 10, 10))
    with pytest.raises(ValueError, match="no se ha cargado"):
        recortar(captura, Caja(0, 0, 0, 0))
