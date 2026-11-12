from __future__ import annotations

import hashlib
import random

from vigia_ocr.dominio.codigo import es_codigo_valido
from vigia_ocr.sintetico.generador import (
    ALTO,
    ANCHO,
    ParametrosRuido,
    codigo_aleatorio,
    generar_lote,
    renderizar,
)


def huella(imagen_bytes: bytes) -> str:
    return hashlib.sha256(imagen_bytes).hexdigest()


def test_misma_semilla_misma_imagen() -> None:
    a = renderizar("AP482133", 42)
    b = renderizar("AP482133", 42)
    assert huella(a.tobytes()) == huella(b.tobytes())


def test_semillas_distintas_dan_ruido_distinto() -> None:
    assert renderizar("AP482133", 1).tobytes() != renderizar("AP482133", 2).tobytes()


def test_dimensiones_y_modo() -> None:
    imagen = renderizar("TE000000", 7)
    assert imagen.size == (ANCHO, ALTO)
    assert imagen.mode == "RGB"


def test_lote_reproducible_con_codigos_validos() -> None:
    lote = generar_lote(25, 2026)
    otra_vez = generar_lote(25, 2026)
    assert [m.codigo for m in lote] == [m.codigo for m in otra_vez]
    assert all(es_codigo_valido(m.codigo) for m in lote)
    assert len({m.codigo[:2] for m in lote}) == 5  # aparecen todos los estados


def test_codigo_aleatorio_es_valido() -> None:
    rng = random.Random(9)
    assert all(es_codigo_valido(codigo_aleatorio(rng)) for _ in range(200))


def test_dificultad_cero_produce_imagen_mas_limpia() -> None:
    limpia = renderizar("AP482133", 5, ParametrosRuido(dificultad=0.0))
    ruidosa = renderizar("AP482133", 5)

    def pixeles_oscuros(imagen_bytes: bytes) -> int:
        return sum(1 for b in imagen_bytes[::3] if b < 120)

    assert pixeles_oscuros(limpia.convert("L").tobytes()) < pixeles_oscuros(
        ruidosa.convert("L").tobytes()
    )
