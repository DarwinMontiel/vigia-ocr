"""Adaptador para ddddocr: modelo ONNX liviano entrenado con texto corto y ruidoso."""

from __future__ import annotations

import contextlib
import io
from typing import Any

from PIL import Image

from vigia_ocr.dominio.errores import MotorNoDisponible


class MotorDdddocr:
    nombre = "ddddocr"

    def __init__(self) -> None:
        try:
            import ddddocr
        except ImportError as error:
            raise MotorNoDisponible(
                "ddddocr no está instalado. Instálalo con: pip install -e '.[ocr]'"
            ) from error
        # ddddocr imprime un aviso al iniciar; lo silenciamos para no ensuciar los logs.
        with contextlib.redirect_stdout(io.StringIO()):
            self._ocr: Any = ddddocr.DdddOcr(show_ad=False)

    def leer(self, imagen: Image.Image) -> str:
        return str(self._ocr.classification(imagen.convert("RGB")))
