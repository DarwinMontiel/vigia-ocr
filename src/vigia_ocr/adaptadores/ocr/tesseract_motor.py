"""Adaptador para Tesseract (vía pytesseract). Requiere el binario ``tesseract`` en el PATH."""

from __future__ import annotations

from typing import Any

import structlog
from PIL import Image

from vigia_ocr.dominio.codigo import ALFABETO
from vigia_ocr.dominio.errores import MotorNoDisponible

log = structlog.get_logger(__name__)

# --psm 7: una sola línea de texto. --oem 1: motor LSTM. Lista blanca = alfabeto del código.
CONFIGURACION = f"--psm 7 --oem 1 -c tessedit_char_whitelist={ALFABETO}"


class MotorTesseract:
    nombre = "tesseract"

    def __init__(self, configuracion: str = CONFIGURACION) -> None:
        try:
            import pytesseract
        except ImportError as error:
            raise MotorNoDisponible(
                "pytesseract no está instalado. Instálalo con: pip install -e '.[ocr]'"
            ) from error
        try:
            pytesseract.get_tesseract_version()
        except pytesseract.TesseractNotFoundError as error:
            raise MotorNoDisponible(
                "No se encontró el binario de Tesseract. En Ubuntu: "
                "sudo apt-get install tesseract-ocr; en Windows: instalador de UB Mannheim"
            ) from error
        self._tesseract: Any = pytesseract
        self._configuracion = configuracion

    def leer(self, imagen: Image.Image) -> str:
        # Tesseract 5 termina con SIGFPE (código -8) en algunas imágenes muy ruidosas, de
        # forma intermitente. Se reintenta una vez; si vuelve a fallar, cuenta como lectura
        # vacía (pierde la votación) en lugar de tumbar la cadena.
        for intento in (1, 2):
            try:
                texto = self._tesseract.image_to_string(imagen, config=self._configuracion)
            except self._tesseract.TesseractError as error:
                log.debug("Tesseract terminó con error", intento=intento, error=str(error))
                continue
            return str(texto).strip()
        return ""
