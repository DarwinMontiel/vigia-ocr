"""Reglas de la arquitectura hexagonal, verificadas en cada ejecución de pruebas.

El núcleo (``dominio`` y ``aplicacion``) no puede importar adaptadores ni librerías de
infraestructura. Si alguien agrega ``import selenium`` en un caso de uso, esta prueba falla.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).parents[2] / "src" / "vigia_ocr"

PROHIBIDOS_EN_NUCLEO = (
    "vigia_ocr.adaptadores",
    "vigia_ocr.portal_ficticio",
    "vigia_ocr.cli",
    "vigia_ocr.contenedor",
    "vigia_ocr.config",
    "selenium",
    "sqlalchemy",
    "cv2",
    "ddddocr",
    "easyocr",
    "pytesseract",
    "fastapi",
    "pyodbc",
)
# El dominio es aún más estricto: ni siquiera depende de los puertos ni de Pillow.
PROHIBIDOS_EN_DOMINIO = (*PROHIBIDOS_EN_NUCLEO, "vigia_ocr.aplicacion", "vigia_ocr.puertos", "PIL")


def importaciones(archivo: Path) -> set[str]:
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    modulos: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            modulos.add(nodo.module)
    return modulos


def violaciones(paquete: str, prohibidos: tuple[str, ...]) -> list[str]:
    encontradas = []
    for archivo in sorted((RAIZ / paquete).rglob("*.py")):
        for modulo in importaciones(archivo):
            if any(modulo == p or modulo.startswith(p + ".") for p in prohibidos):
                encontradas.append(f"{archivo.relative_to(RAIZ)} importa {modulo}")
    return encontradas


@pytest.mark.parametrize(
    ("paquete", "prohibidos"),
    [
        ("dominio", PROHIBIDOS_EN_DOMINIO),
        ("aplicacion", PROHIBIDOS_EN_NUCLEO),
        ("puertos", PROHIBIDOS_EN_NUCLEO),
    ],
)
def test_el_nucleo_no_depende_de_la_infraestructura(
    paquete: str, prohibidos: tuple[str, ...]
) -> None:
    assert violaciones(paquete, prohibidos) == []


def test_los_adaptadores_no_dependen_entre_si_salvo_dentro_de_su_familia() -> None:
    """Un adaptador de OCR no debe importar el de persistencia, ni viceversa."""
    familias = ["ocr", "persistencia", "portal", "preprocesado"]
    for familia in familias:
        otras = tuple(f"vigia_ocr.adaptadores.{f}" for f in familias if f != familia)
        assert violaciones(f"adaptadores/{familia}", otras) == []
