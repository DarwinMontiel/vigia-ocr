"""Renderiza códigos de estado como imágenes ruidosas, al estilo de un portal público.

Todo el azar sale de ``random.Random(semilla)``: la misma semilla produce exactamente la misma
imagen en cualquier máquina (la fuente es la que trae Pillow, no una del sistema operativo).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from functools import cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from vigia_ocr.dominio.codigo import EstadoObligacion, construir_codigo

ANCHO = 240
ALTO = 72


@dataclass(frozen=True, slots=True)
class ParametrosRuido:
    """Perillas del ruido. ``dificultad`` escala todo a la vez (1.0 = portal de la demo)."""

    dificultad: float = 1.0
    tamano_fuente: int = 32
    rotacion_max: float = 14.0
    lineas: int = 3
    puntos: int = 260
    amplitud_onda: float = 2.5
    ruido_fondo: float = 18.0
    desenfoque: float = 0.6


@dataclass(frozen=True, slots=True)
class Muestra:
    codigo: str
    semilla: int
    imagen: Image.Image


@cache
def _fuente(tamano: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=tamano)


def codigo_aleatorio(rng: random.Random) -> str:
    """Código válido al azar (estado + serie + DV)."""
    estado = rng.choice(list(EstadoObligacion))
    serie = f"{rng.randrange(100000):05d}"
    return construir_codigo(estado, serie)


def _color_tinta(rng: random.Random) -> tuple[int, int, int]:
    base = rng.randint(10, 80)
    return (
        base + rng.randint(0, 60),
        base + rng.randint(0, 60),
        base + rng.randint(0, 60),
    )


def _fondo(rng: random.Random, p: ParametrosRuido) -> Image.Image:
    claro = [rng.randint(200, 245) for _ in range(3)]
    np_rng = np.random.default_rng(rng.getrandbits(32))
    ruido = np_rng.normal(0.0, p.ruido_fondo * p.dificultad, (ALTO, ANCHO, 3))
    gradiente = np.linspace(-12, 12, ANCHO)[None, :, None]
    pixeles = np.clip(np.array(claro, dtype=np.float64) + ruido + gradiente, 0, 255)
    fondo = Image.fromarray(pixeles.astype(np.uint8), "RGB")
    dibujo = ImageDraw.Draw(fondo)
    for _ in range(int(6 * p.dificultad)):  # manchas suaves
        x, y = rng.randint(-20, ANCHO), rng.randint(-20, ALTO)
        r = rng.randint(8, 26)
        tono = tuple(min(255, c + rng.randint(-35, 5)) for c in claro)
        dibujo.ellipse((x, y, x + 2 * r, y + r), fill=(tono[0], tono[1], tono[2]))
    return fondo


def _pegar_caracteres(
    lienzo: Image.Image, codigo: str, rng: random.Random, p: ParametrosRuido
) -> list[tuple[int, int, int]]:
    fuente = _fuente(p.tamano_fuente)
    colores: list[tuple[int, int, int]] = []
    separaciones = [rng.randint(-2, 3) for _ in codigo]
    ancho_texto = sum(int(fuente.getlength(c)) for c in codigo) + sum(separaciones)
    x = max(4, (ANCHO - ancho_texto) // 2 + rng.randint(-8, 8))
    for caracter, separacion in zip(codigo, separaciones, strict=True):
        color = _color_tinta(rng)
        colores.append(color)
        lado = p.tamano_fuente + 12
        celda = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
        ImageDraw.Draw(celda).text((6, 2), caracter, font=fuente, fill=(*color, 255))
        angulo = rng.uniform(-p.rotacion_max, p.rotacion_max) * p.dificultad
        celda = celda.rotate(angulo, resample=Image.Resampling.BICUBIC, expand=False)
        y = rng.randint(4, 14)
        lienzo.paste(celda, (x, y), celda)
        x += int(fuente.getlength(caracter)) + separacion
    return colores


def _lineas_interferencia(
    lienzo: Image.Image, rng: random.Random, p: ParametrosRuido, colores: list[tuple[int, int, int]]
) -> None:
    dibujo = ImageDraw.Draw(lienzo)
    for _ in range(round(p.lineas * p.dificultad)):
        color = rng.choice(colores)
        amplitud = rng.uniform(4, 16)
        fase = rng.uniform(0, 2 * math.pi)
        periodo = rng.uniform(60, 200)
        base = rng.uniform(15, ALTO - 15)
        x0, x1 = rng.randint(0, ANCHO // 3), rng.randint(2 * ANCHO // 3, ANCHO)
        puntos = [
            (float(x), base + amplitud * math.sin(2 * math.pi * x / periodo + fase))
            for x in range(x0, x1, 3)
        ]
        dibujo.line(puntos, fill=color, width=rng.choice((1, 1, 2)))


def _puntos(lienzo: Image.Image, rng: random.Random, p: ParametrosRuido) -> None:
    dibujo = ImageDraw.Draw(lienzo)
    for _ in range(int(p.puntos * p.dificultad)):
        x, y = rng.randrange(ANCHO), rng.randrange(ALTO)
        r = rng.choice((0, 0, 0, 1))
        dibujo.ellipse((x, y, x + r, y + r), fill=_color_tinta(rng))


def _onda(lienzo: Image.Image, rng: random.Random, p: ParametrosRuido) -> Image.Image:
    amplitud = p.amplitud_onda * p.dificultad
    if amplitud <= 0:
        return lienzo
    periodo = rng.uniform(50, 110)
    fase = rng.uniform(0, 2 * math.pi)
    origen = np.asarray(lienzo)
    destino = np.empty_like(origen)
    for x in range(ANCHO):
        desplazamiento = round(amplitud * math.sin(2 * math.pi * x / periodo + fase))
        destino[:, x] = np.roll(origen[:, x], desplazamiento, axis=0)
    return Image.fromarray(destino, "RGB")


def renderizar(codigo: str, semilla: int, parametros: ParametrosRuido | None = None) -> Image.Image:
    """Dibuja ``codigo`` con ruido determinado por ``semilla``."""
    p = parametros or ParametrosRuido()
    rng = random.Random(semilla)
    lienzo = _fondo(rng, p)
    colores = _pegar_caracteres(lienzo, codigo, rng, p)
    _lineas_interferencia(lienzo, rng, p, colores)
    _puntos(lienzo, rng, p)
    lienzo = _onda(lienzo, rng, p)
    if p.desenfoque > 0:
        lienzo = lienzo.filter(ImageFilter.GaussianBlur(p.desenfoque * p.dificultad))
    return lienzo


def generar_lote(
    cantidad: int, semilla: int, parametros: ParametrosRuido | None = None
) -> list[Muestra]:
    """Lote reproducible de muestras con su código verdadero (la "respuesta correcta")."""
    rng = random.Random(semilla)
    muestras = []
    for _ in range(cantidad):
        codigo = codigo_aleatorio(rng)
        semilla_imagen = rng.getrandbits(48)
        muestras.append(
            Muestra(codigo, semilla_imagen, renderizar(codigo, semilla_imagen, parametros))
        )
    return muestras
