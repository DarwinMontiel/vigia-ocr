"""Preprocesado de imágenes con Pillow y OpenCV.

Cada paso es una función pura ``ndarray -> ndarray``. Una ``Variante`` es una cadena de pasos
con nombre; el lector OCR prueba varias variantes porque ninguna sirve para todas las
imágenes: la binarización que limpia un fondo con manchas puede borrar un carácter tenue.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

import cv2
import numpy as np
import numpy.typing as npt
from PIL import Image

Matriz = npt.NDArray[np.uint8]
Paso = Callable[[Matriz], Matriz]


def a_grises(m: Matriz) -> Matriz:
    """Luminancia estándar (ITU-R BT.601)."""
    if m.ndim == 2:
        return m
    return np.asarray(cv2.cvtColor(m, cv2.COLOR_RGB2GRAY), dtype=np.uint8)


def canal_minimo(m: Matriz) -> Matriz:
    """Mínimo entre R, G y B: separa tinta de color de un fondo claro mejor que la luminancia."""
    if m.ndim == 2:
        return m
    return np.asarray(m.min(axis=2), dtype=np.uint8)


def escalar(factor: float) -> Paso:
    """Aumentar la resolución engrosa los trazos antes de binarizar."""

    def paso(m: Matriz) -> Matriz:
        return np.asarray(
            cv2.resize(m, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC),
            dtype=np.uint8,
        )

    return paso


def mediana(tamano: int) -> Paso:
    """Filtro de mediana: elimina ruido de sal y pimienta sin difuminar bordes."""
    if tamano % 2 == 0 or tamano < 3:
        raise ValueError("El tamaño de la mediana debe ser impar y mayor o igual a 3")

    def paso(m: Matriz) -> Matriz:
        return np.asarray(cv2.medianBlur(m, tamano), dtype=np.uint8)

    return paso


def binarizar_otsu(m: Matriz) -> Matriz:
    """Umbral global de Otsu. Deja el texto negro sobre fondo blanco."""
    gris = a_grises(m)
    _, binaria = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    salida = np.asarray(binaria, dtype=np.uint8)
    if salida.mean() < 127:  # si quedó más negro que blanco, el texto quedó invertido
        salida = np.asarray(255 - salida, dtype=np.uint8)
    return salida


def apertura(tamano: int) -> Paso:
    """Apertura morfológica sobre la tinta: borra líneas y puntos más delgados que el kernel."""
    kernel = np.ones((tamano, tamano), np.uint8)

    def paso(m: Matriz) -> Matriz:
        tinta = 255 - m
        abierta = cv2.morphologyEx(tinta, cv2.MORPH_OPEN, kernel)
        return np.asarray(255 - abierta, dtype=np.uint8)

    return paso


def quitar_componentes(area_minima: int) -> Paso:
    """Borra manchas de tinta conectadas con menos de ``area_minima`` píxeles."""

    def paso(m: Matriz) -> Matriz:
        tinta = np.asarray(255 - m, dtype=np.uint8)
        cantidad, etiquetas, estadisticas, _ = cv2.connectedComponentsWithStats(
            tinta, connectivity=8
        )
        areas = estadisticas[:, cv2.CC_STAT_AREA]
        conservar = np.zeros(cantidad, dtype=bool)
        conservar[1:] = areas[1:] >= area_minima
        return np.where(conservar[etiquetas], 0, 255).astype(np.uint8)

    return paso


@dataclass(frozen=True, slots=True)
class Variante:
    """Implementa el puerto ``Preprocesador`` como una cadena de pasos con nombre."""

    nombre: str
    pasos: tuple[Paso, ...] = ()

    def aplicar(self, imagen: Image.Image) -> Image.Image:
        matriz: Matriz = np.asarray(imagen.convert("RGB"), dtype=np.uint8)
        for paso in self.pasos:
            matriz = paso(matriz)
        return Image.fromarray(matriz)


ORIGINAL: Final = Variante("original")
MEDIANA: Final = Variante("mediana", (mediana(3),))
OTSU_X2: Final = Variante("otsu_x2", (a_grises, escalar(2), mediana(3), binarizar_otsu))
OTSU_X2_APERTURA: Final = Variante(
    "otsu_x2_apertura", (a_grises, escalar(2), mediana(3), binarizar_otsu, apertura(3))
)
CANAL_MINIMO: Final = Variante(
    "canal_minimo", (canal_minimo, escalar(2), mediana(3), binarizar_otsu)
)

# Orden de mayor a menor utilidad medida en el banco de evaluación (ver docs/evaluacion.md).
VARIANTES_POR_DEFECTO: Final[tuple[Variante, ...]] = (
    OTSU_X2_APERTURA,
    OTSU_X2,
    CANAL_MINIMO,
    MEDIANA,
    ORIGINAL,
)

CATALOGO: Final[dict[str, Variante]] = {v.nombre: v for v in VARIANTES_POR_DEFECTO}


def variantes_por_nombre(nombres: Sequence[str]) -> tuple[Variante, ...]:
    desconocidas = [n for n in nombres if n not in CATALOGO]
    if desconocidas:
        raise ValueError(
            f"Variantes desconocidas: {', '.join(desconocidas)}. Disponibles: {', '.join(CATALOGO)}"
        )
    return tuple(CATALOGO[n] for n in nombres)
