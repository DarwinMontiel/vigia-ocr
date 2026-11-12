"""Recorte de la imagen de estado a partir de una captura de pantalla completa.

Se recorta de la captura (y no se descarga la URL del ``<img>``) porque la URL suele llevar un
token de un solo uso: pedirla otra vez entrega una imagen distinta a la que el navegador
mostró, o un error. La captura es exactamente lo que vería una persona.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image


@dataclass(frozen=True, slots=True)
class Caja:
    """Rectángulo en píxeles CSS, relativo al viewport (``getBoundingClientRect``)."""

    x: float
    y: float
    ancho: float
    alto: float


def recortar(captura_png: bytes, caja: Caja, escala: float = 1.0) -> Image.Image:
    """Recorta ``caja`` de la captura y la devuelve en su tamaño CSS original.

    ``escala`` es ``window.devicePixelRatio``: en pantallas con zoom o HiDPI la captura tiene
    más píxeles que el CSS, y hay que multiplicar las coordenadas antes de recortar.
    """
    if caja.ancho <= 0 or caja.alto <= 0:
        raise ValueError("La caja a recortar tiene tamaño cero: la imagen no se ha cargado")
    with Image.open(io.BytesIO(captura_png)) as captura:
        captura.load()
        izquierda = round(caja.x * escala)
        arriba = round(caja.y * escala)
        derecha = round((caja.x + caja.ancho) * escala)
        abajo = round((caja.y + caja.alto) * escala)
        if izquierda < 0 or arriba < 0 or derecha > captura.width or abajo > captura.height:
            raise ValueError(
                f"La imagen ({izquierda},{arriba})-({derecha},{abajo}) queda fuera de la "
                f"captura de {captura.width}x{captura.height}"
            )
        recorte = captura.convert("RGB").crop((izquierda, arriba, derecha, abajo))
    tamano_css = (round(caja.ancho), round(caja.alto))
    if recorte.size != tamano_css:
        recorte = recorte.resize(tamano_css, Image.Resampling.LANCZOS)
    return recorte
