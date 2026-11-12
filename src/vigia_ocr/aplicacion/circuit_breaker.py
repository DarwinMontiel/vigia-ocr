"""Circuit breaker para no martillar un portal caído.

    CERRADO ──(N fallos seguidos)──▶ ABIERTO ──(enfriamiento)──▶ SEMIABIERTO
       ▲                                 ▲                          │
       └──────────(prueba exitosa)───────┼──────(prueba falla)──────┘

En CERRADO las llamadas pasan. En ABIERTO se rechazan de inmediato con ``CircuitoAbierto``,
sin tocar el portal. En SEMIABIERTO se deja pasar una sola llamada de prueba.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import TypeVar

import structlog

from vigia_ocr.dominio.errores import CircuitoAbierto, ErrorDeSistema
from vigia_ocr.puertos import Reloj

T = TypeVar("T")

log = structlog.get_logger(__name__)


class EstadoCircuito(StrEnum):
    CERRADO = "cerrado"
    ABIERTO = "abierto"
    SEMIABIERTO = "semiabierto"


class CircuitBreaker:
    def __init__(
        self,
        reloj: Reloj,
        *,
        umbral_fallos: int = 3,
        enfriamiento_s: float = 30.0,
        nombre: str = "portal",
    ) -> None:
        if umbral_fallos < 1:
            raise ValueError("umbral_fallos debe ser al menos 1")
        self._reloj = reloj
        self._umbral = umbral_fallos
        self._enfriamiento = enfriamiento_s
        self._nombre = nombre
        self._estado = EstadoCircuito.CERRADO
        self._fallos_seguidos = 0
        self._abierto_desde = 0.0

    @property
    def estado(self) -> EstadoCircuito:
        if (
            self._estado is EstadoCircuito.ABIERTO
            and self._reloj.monotonico() - self._abierto_desde >= self._enfriamiento
        ):
            self._cambiar(EstadoCircuito.SEMIABIERTO)
        return self._estado

    def llamar(self, operacion: Callable[[], T]) -> T:
        """Ejecuta la operación si el circuito lo permite.

        Solo los ``ErrorDeSistema`` cuentan como fallo: un radicado inexistente es una
        respuesta válida del portal y no debe abrir el circuito.
        """
        if self.estado is EstadoCircuito.ABIERTO:
            restante = self._enfriamiento - (self._reloj.monotonico() - self._abierto_desde)
            raise CircuitoAbierto(max(restante, 0.0))
        try:
            resultado = operacion()
        except ErrorDeSistema:
            self._registrar_fallo()
            raise
        self._registrar_exito()
        return resultado

    def _registrar_exito(self) -> None:
        self._fallos_seguidos = 0
        if self._estado is not EstadoCircuito.CERRADO:
            self._cambiar(EstadoCircuito.CERRADO)

    def _registrar_fallo(self) -> None:
        self._fallos_seguidos += 1
        if self._estado is EstadoCircuito.SEMIABIERTO or self._fallos_seguidos >= self._umbral:
            self._abierto_desde = self._reloj.monotonico()
            self._cambiar(EstadoCircuito.ABIERTO)

    def _cambiar(self, nuevo: EstadoCircuito) -> None:
        if nuevo is self._estado:
            return
        log.warning(
            "Cambio de estado del circuit breaker",
            circuito=self._nombre,
            anterior=self._estado.value,
            nuevo=nuevo.value,
            fallos_seguidos=self._fallos_seguidos,
        )
        self._estado = nuevo
