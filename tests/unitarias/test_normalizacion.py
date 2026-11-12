from __future__ import annotations

import pytest

from vigia_ocr.dominio.normalizacion import limpiar, normalizar


@pytest.mark.parametrize(
    ("crudo", "esperado"),
    [
        ("AP482136", "AP482136"),
        ("ap482136", "AP482136"),
        (" AP 4821 36 ", "AP482136"),
        ("AP48Z13G", "AP482136"),  # Z→2, G→6 en posiciones de dígito
        ("4PO82I36", "AP082136"),  # 4→A en letra; O→0, I→1 en dígito
        ("5UO0O0O0", "SU000000"),  # 5→S en letra
        ("7E8B8B8B", "TE888888"),  # 7→T en letra, B→8 en dígito
        ("VC1|2!34", "UC112134"),  # V→U; |, ! → 1
        ("AP4821$3", "AP482153"),
        ("EMbgq123", "EM699123"),  # minúsculas ambiguas en dígitos
    ],
)
def test_normaliza_confusiones_segun_la_posicion(crudo: str, esperado: str) -> None:
    assert normalizar(crudo) == esperado


@pytest.mark.parametrize(
    ("crudo", "esperado"), [("AP4821", "AP4821"), ("ap48213699", "AP48213699")]
)
def test_longitud_incorrecta_solo_limpia(crudo: str, esperado: str) -> None:
    assert normalizar(crudo) == esperado


def test_no_inventa_caracteres_faltantes() -> None:
    assert len(normalizar("AP48 13")) == 6


def test_limpiar_quita_signos_inventados() -> None:
    assert limpiar("«AP-482.136»\n") == "AP482136"
