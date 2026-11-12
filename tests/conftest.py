"""Dobles de prueba compartidos. Implementan los puertos sin infraestructura real."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

import pytest
import structlog
from PIL import Image

from vigia_ocr.dominio.codigo import EstadoObligacion, construir_codigo
from vigia_ocr.dominio.errores import PortalNoDisponible, RadicadoInexistente
from vigia_ocr.dominio.modelos import Radicado

FECHA_CORTE = date(2026, 11, 12)


def codigo_ejemplo(
    serie: str = "48213", estado: EstadoObligacion = EstadoObligacion.ACUERDO_DE_PAGO
) -> str:
    return construir_codigo(estado, serie)


def imagen_con_texto(texto: str) -> Image.Image:
    """Imagen "falsa" que lleva el texto codificado en la primera fila de píxeles.

    Sobrevive a conversiones (``convert("RGB")``, ``np.asarray``) que sí perderían los
    metadatos, así que pasa intacta por las variantes de preprocesado reales.
    """
    imagen = Image.new("RGB", (32, 8), "white")
    for posicion, caracter in enumerate(texto[:31]):
        imagen.putpixel((posicion, 0), (ord(caracter), 1, 1))
    imagen.putpixel((min(len(texto), 31), 0), (0, 0, 0))
    return imagen


def texto_de_imagen(imagen: Image.Image) -> str:
    rgb = imagen.convert("RGB")
    caracteres = []
    for posicion in range(rgb.width):
        pixel = rgb.getpixel((posicion, 0))
        assert isinstance(pixel, tuple)
        if pixel[1:] != (1, 1):
            break
        caracteres.append(chr(pixel[0]))
    return "".join(caracteres)


class MotorGuion:
    """Motor OCR falso: devuelve los textos de un guion, en orden (y luego repite el último)."""

    def __init__(self, nombre: str, guion: Iterable[str] | Callable[[Image.Image], str]) -> None:
        self.nombre = nombre
        self.llamadas = 0
        if callable(guion):
            self._funcion: Callable[[Image.Image], str] | None = guion
            self._guion: list[str] = []
        else:
            self._funcion = None
            self._guion = list(guion)

    def leer(self, imagen: Image.Image) -> str:
        self.llamadas += 1
        if self._funcion is not None:
            return self._funcion(imagen)
        indice = min(self.llamadas - 1, len(self._guion) - 1)
        return self._guion[indice]


class MotorQueLeeMetadatos:
    """Motor falso que "lee" el texto codificado por ``imagen_con_texto``."""

    def __init__(self, nombre: str = "metadatos") -> None:
        self.nombre = nombre
        self.llamadas = 0

    def leer(self, imagen: Image.Image) -> str:
        self.llamadas += 1
        return texto_de_imagen(imagen)


@dataclass
class VarianteIdentidad:
    nombre: str = "identidad"
    aplicaciones: int = 0

    def aplicar(self, imagen: Image.Image) -> Image.Image:
        self.aplicaciones += 1
        return imagen


@dataclass
class PortalGuion:
    """Portal falso. Cada radicado tiene una cola de respuestas: textos o excepciones."""

    respuestas: dict[str, list[str | Exception]] = field(default_factory=dict)
    llamadas: list[str] = field(default_factory=list)
    caido: bool = False

    def obtener_imagen_estado(self, radicado: Radicado) -> Image.Image:
        self.llamadas.append(radicado.valor)
        if self.caido:
            raise PortalNoDisponible("portal caído (simulado)")
        cola = self.respuestas.get(radicado.valor)
        if cola is None:
            raise RadicadoInexistente(f"No existe un proceso con el radicado {radicado}")
        respuesta = cola.pop(0) if len(cola) > 1 else cola[0]
        if isinstance(respuesta, Exception):
            raise respuesta
        return imagen_con_texto(respuesta)


class RelojFalso:
    def __init__(self) -> None:
        self._monotonico = 1000.0
        self._ahora = datetime(2026, 11, 12, 6, 0, tzinfo=UTC)

    def ahora(self) -> datetime:
        return self._ahora

    def monotonico(self) -> float:
        return self._monotonico

    def avanzar(self, segundos: float) -> None:
        self._monotonico += segundos
        self._ahora += timedelta(seconds=segundos)


@pytest.fixture(autouse=True)
def _registro_por_defecto() -> Iterator[None]:
    """Cada prueba arranca con la configuración de structlog por defecto."""
    yield
    structlog.reset_defaults()


@pytest.fixture
def reloj() -> RelojFalso:
    return RelojFalso()


@pytest.fixture
def radicados() -> list[Radicado]:
    return [Radicado(f"PCA-2026-{n:05d}") for n in (17, 23, 31)]
