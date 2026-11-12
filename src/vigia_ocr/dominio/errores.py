"""Excepciones del dominio. Separan errores de negocio (no reintentar) de los de sistema."""

from __future__ import annotations


class ErrorVigia(Exception):
    """Base de todos los errores propios de Vigía OCR."""


class ErrorDeNegocio(ErrorVigia):
    """El caso no se puede resolver reintentando (dato de entrada o respuesta definitiva)."""


class ErrorDeSistema(ErrorVigia):
    """Falla transitoria de infraestructura: tiene sentido reintentar más tarde."""


class RadicadoInexistente(ErrorDeNegocio):
    """El portal respondió que el radicado no existe."""


class PortalNoDisponible(ErrorDeSistema):
    """El portal no respondió, respondió con error o cambió su estructura."""


class CircuitoAbierto(ErrorDeSistema):
    """El circuit breaker está abierto: no se llama al portal hasta que se enfríe."""

    def __init__(self, segundos_restantes: float) -> None:
        super().__init__(
            f"Circuito abierto: el portal falló varias veces seguidas; "
            f"se reintentará en {segundos_restantes:.0f} s"
        )
        self.segundos_restantes = segundos_restantes


class MotorNoDisponible(ErrorDeSistema):
    """El motor OCR no está instalado o no pudo inicializarse."""


class ErrorVerificacion(ErrorDeSistema):
    """Lo leído de la base de datos después de guardar no coincide con lo que se guardó."""
