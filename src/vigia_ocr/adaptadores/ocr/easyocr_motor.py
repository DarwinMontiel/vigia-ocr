"""Adaptador para EasyOCR (PyTorch). Es el motor más pesado: va de último en la cadena."""

from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image

from vigia_ocr.dominio.codigo import ALFABETO
from vigia_ocr.dominio.errores import MotorNoDisponible


class MotorEasyOCR:
    nombre = "easyocr"

    def __init__(self) -> None:
        try:
            import easyocr
        except ImportError as error:
            raise MotorNoDisponible(
                "EasyOCR no está instalado (trae PyTorch). Instálalo con: "
                "pip install -e '.[easyocr]'"
            ) from error
        try:
            # La primera vez descarga los pesos del modelo (~100 MB) a ~/.EasyOCR.
            self._lector: Any = easyocr.Reader(["en"], gpu=False, verbose=False)
        except (OSError, RuntimeError) as error:
            raise MotorNoDisponible(f"EasyOCR no pudo inicializarse: {error}") from error

    def leer(self, imagen: Image.Image) -> str:
        fragmentos = self._lector.readtext(
            np.asarray(imagen.convert("RGB")), detail=0, allowlist=ALFABETO, paragraph=False
        )
        return "".join(str(f) for f in fragmentos)
