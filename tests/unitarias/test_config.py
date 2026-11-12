from __future__ import annotations

import pytest
from pydantic import ValidationError

from vigia_ocr.config import Configuracion


def test_valores_por_defecto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIGIA_MOTORES", raising=False)
    config = Configuracion(_env_file=None)  # type: ignore[call-arg]
    assert config.motores == ["ddddocr", "tesseract", "easyocr"]
    assert config.max_imagenes == 3
    assert config.base_datos_url.startswith("sqlite")


def test_listas_separadas_por_comas_desde_el_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGIA_MOTORES", "tesseract, ddddocr")
    monkeypatch.setenv("VIGIA_VARIANTES", "original,otsu_x2")
    monkeypatch.setenv("VIGIA_MAX_IMAGENES", "5")
    config = Configuracion(_env_file=None)  # type: ignore[call-arg]
    assert config.motores == ["tesseract", "ddddocr"]
    assert config.variantes == ["original", "otsu_x2"]
    assert config.max_imagenes == 5


@pytest.mark.parametrize(
    ("variable", "valor", "mensaje"),
    [
        ("VIGIA_MOTORES", "ddddocr,magia", "Motores desconocidos: magia"),
        ("VIGIA_VARIANTES", "sepia", "Variantes desconocidas: sepia"),
        ("VIGIA_MAX_IMAGENES", "0", "greater than or equal"),
        ("VIGIA_LOG_FORMATO", "xml", "consola"),
    ],
)
def test_valores_invalidos_fallan_al_arrancar(
    monkeypatch: pytest.MonkeyPatch, variable: str, valor: str, mensaje: str
) -> None:
    monkeypatch.setenv(variable, valor)
    with pytest.raises(ValidationError, match=mensaje):
        Configuracion(_env_file=None)  # type: ignore[call-arg]
