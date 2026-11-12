"""Código de estado que el portal publica como imagen y sus reglas de validación.

Formato: dos letras de estado + cinco dígitos de serie + un dígito de verificación (Luhn).

    AP 48213 3
    │  │     └─ dígito de verificación sobre los cinco dígitos de serie
    │  └─────── serie de la actuación
    └────────── estado de la obligación (AC, AP, EM, SU, TE)

La validación es la segunda red de seguridad del OCR: una lectura que no cumple el patrón o
cuyo dígito de verificación no cuadra se descarta, en lugar de guardarse como dato malo.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Final


class EstadoObligacion(StrEnum):
    """Estado procesal de la obligación según el portal."""

    ACTIVA = "AC"
    ACUERDO_DE_PAGO = "AP"
    EMBARGO = "EM"
    SUSPENDIDA = "SU"
    TERMINADA = "TE"

    @property
    def descripcion(self) -> str:
        return _DESCRIPCIONES[self]


_DESCRIPCIONES: Final[dict[EstadoObligacion, str]] = {
    EstadoObligacion.ACTIVA: "Activa en cobro",
    EstadoObligacion.ACUERDO_DE_PAGO: "Con acuerdo de pago",
    EstadoObligacion.EMBARGO: "Embargo decretado",
    EstadoObligacion.SUSPENDIDA: "Proceso suspendido",
    EstadoObligacion.TERMINADA: "Terminada por pago",
}

PREFIJOS: Final[frozenset[str]] = frozenset(e.value for e in EstadoObligacion)
LETRAS_VALIDAS: Final[str] = "".join(sorted(set("".join(PREFIJOS))))
ALFABETO: Final[str] = LETRAS_VALIDAS + "0123456789"
LONGITUD: Final[int] = 8

PATRON_CODIGO: Final[re.Pattern[str]] = re.compile(r"^(AC|AP|EM|SU|TE)(\d{5})(\d)$")


def digito_verificacion(serie: str) -> int:
    """Calcula el dígito de verificación Luhn (mod 10) de una serie numérica.

    Luhn detecta el 100 % de los errores de un solo dígito y casi todas las transposiciones
    de dígitos adyacentes, que son justo los errores típicos de un OCR.
    """
    if not serie.isdigit():
        raise ValueError(f"La serie debe ser numérica, se recibió {serie!r}")
    total = 0
    for posicion, caracter in enumerate(reversed(serie)):
        valor = int(caracter)
        if posicion % 2 == 0:
            valor *= 2
            if valor > 9:
                valor -= 9
        total += valor
    return (10 - total % 10) % 10


def construir_codigo(estado: EstadoObligacion, serie: str) -> str:
    """Arma un código válido a partir del estado y la serie de cinco dígitos."""
    if len(serie) != 5 or not serie.isdigit():
        raise ValueError(f"La serie debe tener cinco dígitos, se recibió {serie!r}")
    return f"{estado.value}{serie}{digito_verificacion(serie)}"


def es_codigo_valido(texto: str) -> bool:
    """True si el texto cumple el patrón y su dígito de verificación cuadra."""
    coincidencia = PATRON_CODIGO.fullmatch(texto)
    if coincidencia is None:
        return False
    serie, dv = coincidencia.group(2), coincidencia.group(3)
    return digito_verificacion(serie) == int(dv)


def estado_de(codigo: str) -> EstadoObligacion:
    """Estado correspondiente a un código ya validado."""
    if not es_codigo_valido(codigo):
        raise ValueError(f"Código inválido: {codigo!r}")
    return EstadoObligacion(codigo[:2])
