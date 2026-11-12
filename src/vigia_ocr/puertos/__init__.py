"""Puertos: los contratos que el núcleo necesita del mundo exterior.

El núcleo (``dominio`` y ``aplicacion``) depende solo de estas interfaces. Los adaptadores
(``adaptadores/*``) las implementan con Selenium, SQLAlchemy, ddddocr, Tesseract, etc.
Cambiar de motor OCR o de base de datos es escribir un adaptador nuevo, no tocar el núcleo.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Protocol, runtime_checkable

from PIL import Image

from vigia_ocr.dominio.modelos import Radicado, ResultadoConsulta


@runtime_checkable
class MotorOCR(Protocol):
    """Convierte una imagen en texto. No valida ni normaliza: eso es del núcleo."""

    @property
    def nombre(self) -> str: ...

    def leer(self, imagen: Image.Image) -> str: ...


class Preprocesador(Protocol):
    """Transforma una imagen para facilitar la lectura (escala de grises, binarización...)."""

    @property
    def nombre(self) -> str: ...

    def aplicar(self, imagen: Image.Image) -> Image.Image: ...


class PortalConsultas(Protocol):
    """Fuente de la imagen con el estado de un radicado.

    Cada llamada debe devolver una imagen *recién generada* por el portal: si una lectura no es
    confiable, pedir otra imagen es la forma más barata de mejorar el acierto.

    Errores esperados: ``RadicadoInexistente`` (negocio) y ``PortalNoDisponible`` (sistema).
    """

    def obtener_imagen_estado(self, radicado: Radicado) -> Image.Image: ...


class RepositorioResultados(Protocol):
    """Persistencia de resultados con semántica idempotente por (radicado, fecha de corte)."""

    def obtener(self, radicado: Radicado, fecha_corte: date) -> ResultadoConsulta | None: ...

    def guardar(self, resultado: ResultadoConsulta) -> bool:
        """Guarda el resultado. Devuelve False si ya existía (no lo sobrescribe)."""
        ...


class Reloj(Protocol):
    """Fuente de tiempo inyectable: hace deterministas las pruebas del circuit breaker."""

    def ahora(self) -> datetime: ...

    def monotonico(self) -> float: ...
