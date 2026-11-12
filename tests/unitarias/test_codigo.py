from __future__ import annotations

import pytest

from vigia_ocr.dominio.codigo import (
    ALFABETO,
    PREFIJOS,
    EstadoObligacion,
    construir_codigo,
    digito_verificacion,
    es_codigo_valido,
    estado_de,
)


@pytest.mark.parametrize(
    ("serie", "esperado"),
    [
        ("00000", 0),
        # 48213: de derecha a izquierda 3·2=6, 1, 2·2=4, 8, 4·2=8 → 27 → (10 − 7) = 3
        ("48213", 3),
        # 79927: 7·2=14→5, 2, 9·2=18→9, 9, 7·2=14→5 → 30 → 0
        ("79927", 0),
        ("12345", 5),
    ],
)
def test_digito_verificacion_valores_conocidos(serie: str, esperado: int) -> None:
    assert digito_verificacion(serie) == esperado


def test_digito_verificacion_rechaza_no_numericos() -> None:
    with pytest.raises(ValueError, match="numérica"):
        digito_verificacion("12a45")


def test_construir_codigo_y_validarlo() -> None:
    codigo = construir_codigo(EstadoObligacion.EMBARGO, "10974")
    assert len(codigo) == 8
    assert codigo.startswith("EM10974")
    assert es_codigo_valido(codigo)
    assert estado_de(codigo) is EstadoObligacion.EMBARGO


@pytest.mark.parametrize("serie", ["1234", "123456", "12a45"])
def test_construir_codigo_exige_cinco_digitos(serie: str) -> None:
    with pytest.raises(ValueError, match="cinco dígitos"):
        construir_codigo(EstadoObligacion.ACTIVA, serie)


@pytest.mark.parametrize(
    "texto",
    ["", "AP48213", "AP4821366", "XX482136", "ap482136", "AP-48213-6", "AP48213O"],
)
def test_textos_que_no_cumplen_el_patron(texto: str) -> None:
    assert not es_codigo_valido(texto)


def test_el_dv_detecta_todo_error_de_un_solo_digito() -> None:
    """Propiedad de Luhn que justifica su uso: ningún error de un dígito pasa la validación."""
    codigo = construir_codigo(EstadoObligacion.ACUERDO_DE_PAGO, "48213")
    for posicion in range(2, 8):
        for digito in "0123456789":
            if digito == codigo[posicion]:
                continue
            alterado = codigo[:posicion] + digito + codigo[posicion + 1 :]
            assert not es_codigo_valido(alterado), alterado


def test_el_dv_detecta_transposiciones_adyacentes_de_la_serie() -> None:
    detectadas = total = 0
    for numero in range(0, 100000, 37):
        serie = f"{numero:05d}"
        codigo = construir_codigo(EstadoObligacion.ACTIVA, serie)
        for i in range(2, 6):
            if codigo[i] == codigo[i + 1]:
                continue
            total += 1
            alterado = codigo[:i] + codigo[i + 1] + codigo[i] + codigo[i + 2 :]
            detectadas += not es_codigo_valido(alterado)
    # Luhn no detecta 09↔90; todo lo demás sí.
    assert detectadas / total > 0.97


def test_estado_de_codigo_invalido() -> None:
    with pytest.raises(ValueError, match="inválido"):
        estado_de("AP482137")


def test_alfabeto_y_descripciones() -> None:
    assert set(ALFABETO) == set("ACEMPSTU0123456789")
    assert {"AC", "AP", "EM", "SU", "TE"} == PREFIJOS
    assert all(e.descripcion for e in EstadoObligacion)
