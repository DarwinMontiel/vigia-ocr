"""Motores OCR intercambiables. Cada uno importa su librería de forma perezosa.

Así el paquete se instala y se prueba sin PyTorch ni Tesseract: el error aparece solo si se
pide un motor que no está instalado, con un mensaje que dice cómo instalarlo.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Final

from vigia_ocr.dominio.errores import MotorNoDisponible
from vigia_ocr.puertos import MotorOCR


def _ddddocr() -> MotorOCR:
    from vigia_ocr.adaptadores.ocr.ddddocr_motor import MotorDdddocr

    return MotorDdddocr()


def _tesseract() -> MotorOCR:
    from vigia_ocr.adaptadores.ocr.tesseract_motor import MotorTesseract

    return MotorTesseract()


def _easyocr() -> MotorOCR:
    from vigia_ocr.adaptadores.ocr.easyocr_motor import MotorEasyOCR

    return MotorEasyOCR()


FABRICAS: Final[dict[str, Callable[[], MotorOCR]]] = {
    "ddddocr": _ddddocr,
    "tesseract": _tesseract,
    "easyocr": _easyocr,
}


def crear_motores(nombres: Sequence[str], *, omitir_no_disponibles: bool = False) -> list[MotorOCR]:
    """Instancia los motores pedidos, en el orden dado (conviene: del más rápido al más lento)."""
    motores: list[MotorOCR] = []
    for nombre in nombres:
        fabrica = FABRICAS.get(nombre)
        if fabrica is None:
            raise ValueError(
                f"Motor OCR desconocido: {nombre!r}. Disponibles: {', '.join(FABRICAS)}"
            )
        try:
            motores.append(fabrica())
        except MotorNoDisponible:
            if not omitir_no_disponibles:
                raise
    if not motores:
        raise MotorNoDisponible("Ningún motor OCR está disponible en este entorno")
    return motores
