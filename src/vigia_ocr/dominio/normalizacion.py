"""Normalización posicional de lecturas OCR.

Los motores confunden caracteres de forma predecible: ``0`` y ``O``, ``5`` y ``S``, ``8`` y
``B``. Como el formato del código es fijo (dos letras + seis dígitos), cada posición sabe qué
tipo de carácter espera y puede corregir la confusión sin adivinar.
"""

from __future__ import annotations

import re
from typing import Final

from vigia_ocr.dominio.codigo import LONGITUD

# Confusiones típicas cuando se espera un dígito.
_A_DIGITO: Final[dict[str, str]] = {
    "O": "0", "Q": "0", "D": "0", "U": "0",
    "I": "1", "L": "1", "|": "1", "!": "1", "J": "1",
    "Z": "2",
    "S": "5", "$": "5",
    "G": "6", "b": "6",
    "T": "7",
    "B": "8",
    "g": "9", "q": "9",
    "A": "4",
}  # fmt: skip

# Confusiones típicas cuando se espera una letra del alfabeto de estados.
_A_LETRA: Final[dict[str, str]] = {
    "4": "A",
    "G": "C", "(": "C", "[": "C",
    "3": "E", "F": "E",
    "R": "P",
    "5": "S", "$": "S",
    "7": "T",
    "V": "U",
}  # fmt: skip

_RUIDO: Final[re.Pattern[str]] = re.compile(r"[^0-9A-Za-z|!$(\[]")


def limpiar(texto: str) -> str:
    """Quita espacios y signos que los motores suelen inventar alrededor del texto."""
    return _RUIDO.sub("", texto)


def normalizar(texto: str) -> str:
    """Corrige confusiones según la posición. Si la longitud no es la esperada, solo limpia.

    No intenta "rellenar" caracteres faltantes: una lectura incompleta debe perder la votación,
    no convertirse en un código inventado.
    """
    limpio = limpiar(texto)
    if len(limpio) != LONGITUD:
        return limpio.upper()
    letras = "".join(_A_LETRA.get(c.upper(), c.upper()) for c in limpio[:2])
    digitos = "".join(_A_DIGITO.get(c, _A_DIGITO.get(c.upper(), c)) for c in limpio[2:])
    return letras + digitos.upper()
