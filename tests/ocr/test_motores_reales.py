"""Motores OCR reales sobre imágenes sintéticas (``pytest -m ocr``).

Los umbrales son conservadores a propósito: el número fino lo da ``vigia evaluar``; aquí se
verifica que cada motor funcione y que la cadena completa no entregue códigos equivocados.
"""

from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from vigia_ocr.adaptadores.ocr import FABRICAS, crear_motores
from vigia_ocr.adaptadores.preprocesado import VARIANTES_POR_DEFECTO
from vigia_ocr.aplicacion.lector import LectorConsenso
from vigia_ocr.dominio.errores import MotorNoDisponible
from vigia_ocr.dominio.normalizacion import normalizar
from vigia_ocr.puertos import MotorOCR
from vigia_ocr.sintetico.generador import ParametrosRuido, generar_lote, renderizar

pytestmark = pytest.mark.ocr


def motor_o_saltar(nombre: str) -> MotorOCR:
    try:
        return FABRICAS[nombre]()
    except MotorNoDisponible as error:
        pytest.skip(str(error))


def imagen_limpia(texto: str) -> Image.Image:
    from PIL import ImageFont

    imagen = Image.new("RGB", (260, 80), "white")
    ImageDraw.Draw(imagen).text((16, 18), texto, font=ImageFont.load_default(size=36), fill="black")
    return imagen


@pytest.mark.parametrize("nombre", ["ddddocr", "tesseract"])
def test_motor_lee_texto_limpio(nombre: str) -> None:
    motor = motor_o_saltar(nombre)
    assert isinstance(motor, MotorOCR)
    assert normalizar(motor.leer(imagen_limpia("AP482133"))) == "AP482133"


def test_ddddocr_sobre_imagenes_sin_ruido() -> None:
    motor = motor_o_saltar("ddddocr")
    limpias = generar_lote(20, 77, ParametrosRuido(dificultad=0.0))
    aciertos = sum(normalizar(motor.leer(m.imagen)) == m.codigo for m in limpias)
    assert aciertos >= 18


def test_cadena_completa_no_entrega_codigos_equivocados() -> None:
    motores = crear_motores(["ddddocr", "tesseract"], omitir_no_disponibles=True)
    lector = LectorConsenso.desde_motores(motores, VARIANTES_POR_DEFECTO)
    muestras = generar_lote(40, 99)
    aciertos = errores = 0
    for muestra in muestras:
        codigo = None
        for intento in range(3):
            imagen = muestra.imagen if intento == 0 else renderizar(muestra.codigo, intento)
            codigo = lector.leer(imagen).codigo
            if codigo:
                break
        aciertos += codigo == muestra.codigo
        errores += codigo is not None and codigo != muestra.codigo
    assert errores == 0
    assert aciertos >= 34  # ≥ 85 % con solo ddddocr; el banco documenta el número exacto
