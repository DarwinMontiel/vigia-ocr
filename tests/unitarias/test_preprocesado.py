from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from vigia_ocr.adaptadores.preprocesado import (
    CATALOGO,
    VARIANTES_POR_DEFECTO,
    Matriz,
    a_grises,
    apertura,
    binarizar_otsu,
    canal_minimo,
    escalar,
    mediana,
    quitar_componentes,
    variantes_por_nombre,
)
from vigia_ocr.sintetico.generador import generar_lote


def lienzo_blanco(alto: int = 40, ancho: int = 80) -> Matriz:
    return np.full((alto, ancho), 255, dtype=np.uint8)


def test_grises_y_canal_minimo() -> None:
    color = np.zeros((2, 2, 3), dtype=np.uint8)
    color[..., 0] = 200  # rojo fuerte, verde y azul en cero
    assert a_grises(color).shape == (2, 2)
    assert canal_minimo(color).max() == 0  # el mínimo delata la tinta de color
    gris = lienzo_blanco()
    assert a_grises(gris) is gris
    assert canal_minimo(gris) is gris


def test_escalar_duplica_dimensiones() -> None:
    assert escalar(2)(lienzo_blanco(10, 20)).shape == (20, 40)


def test_mediana_borra_sal_y_pimienta() -> None:
    m = lienzo_blanco()
    m[10, 10] = 0
    assert mediana(3)(m)[10, 10] == 255


@pytest.mark.parametrize("tamano", [2, 1, 4])
def test_mediana_exige_tamano_impar(tamano: int) -> None:
    with pytest.raises(ValueError, match="impar"):
        mediana(tamano)


def test_otsu_deja_texto_negro_sobre_blanco() -> None:
    m = np.full((40, 80), 220, dtype=np.uint8)
    m[10:30, 10:20] = 40
    binaria = binarizar_otsu(m)
    assert set(np.unique(binaria)) == {0, 255}
    assert binaria[20, 15] == 0
    assert binaria[2, 2] == 255


def test_otsu_corrige_imagen_invertida() -> None:
    m = np.full((40, 80), 30, dtype=np.uint8)  # fondo oscuro, texto claro
    m[10:30, 10:20] = 230
    binaria = binarizar_otsu(m)
    assert binaria[2, 2] == 255  # el fondo terminó blanco
    assert binaria[20, 15] == 0


def test_apertura_borra_lineas_delgadas_y_conserva_trazos_gruesos() -> None:
    m = lienzo_blanco()
    m[20, :] = 0  # línea de interferencia de 1 px
    m[5:35, 30:38] = 0  # trazo de un carácter
    limpia = apertura(3)(m)
    assert limpia[20, 5] == 255
    assert limpia[20, 34] == 0


def test_quitar_componentes_pequenos() -> None:
    m = lienzo_blanco()
    m[3:5, 3:5] = 0  # punto de 4 px
    m[10:30, 40:50] = 0  # bloque de 200 px
    limpia = quitar_componentes(20)(m)
    assert limpia[4, 4] == 255
    assert limpia[20, 45] == 0


def test_variantes_devuelven_imagenes_pil_sin_mutar_la_original() -> None:
    muestra = generar_lote(1, 3)[0]
    original = muestra.imagen.copy()
    for variante in VARIANTES_POR_DEFECTO:
        salida = variante.aplicar(muestra.imagen)
        assert isinstance(salida, Image.Image)
        assert salida.width >= muestra.imagen.width
    assert original.tobytes() == muestra.imagen.tobytes()


def test_variantes_binarias_solo_tienen_blanco_y_negro() -> None:
    imagen = generar_lote(1, 4)[0].imagen
    salida = np.asarray(CATALOGO["otsu_x2_apertura"].aplicar(imagen))
    assert set(np.unique(salida)) <= {0, 255}


def test_variantes_por_nombre() -> None:
    assert [v.nombre for v in variantes_por_nombre(["original", "otsu_x2"])] == [
        "original",
        "otsu_x2",
    ]
    with pytest.raises(ValueError, match="desconocidas: magia"):
        variantes_por_nombre(["magia"])
