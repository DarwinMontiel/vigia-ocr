"""CLI de punta a punta, con los adaptadores pesados (Selenium, motores OCR) reemplazados."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from types import TracebackType

import pytest
from PIL import Image
from typer.testing import CliRunner

from tests.conftest import MotorGuion, MotorQueLeeMetadatos, imagen_con_texto
from vigia_ocr import cli
from vigia_ocr.adaptadores import ocr as modulo_ocr
from vigia_ocr.adaptadores.portal import selenium_portal
from vigia_ocr.config import obtener_configuracion
from vigia_ocr.dominio.errores import MotorNoDisponible, RadicadoInexistente
from vigia_ocr.dominio.modelos import Radicado
from vigia_ocr.portal_ficticio import catalogo

runner = CliRunner()


@pytest.fixture(autouse=True)
def entorno(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIGIA_BASE_DATOS_URL", f"sqlite:///{tmp_path / 'cli.db'}")
    monkeypatch.setenv("VIGIA_MOTORES", "ddddocr,tesseract")
    monkeypatch.setenv("VIGIA_VARIANTES", "original")
    obtener_configuracion.cache_clear()
    yield
    obtener_configuracion.cache_clear()


@pytest.fixture
def motores_falsos(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_disponible() -> MotorQueLeeMetadatos:
        raise MotorNoDisponible("tesseract no instalado (simulado)")

    monkeypatch.setitem(modulo_ocr.FABRICAS, "ddddocr", lambda: MotorQueLeeMetadatos("ddddocr"))
    monkeypatch.setitem(modulo_ocr.FABRICAS, "tesseract", no_disponible)


class NavegadorFalso:
    """Reemplaza a PortalSelenium: responde con el código verdadero del catálogo."""

    def __init__(self, url_base: str, **_opciones: object) -> None:
        self.url_base = url_base

    def __enter__(self) -> NavegadorFalso:
        return self

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        return None

    def obtener_imagen_estado(self, radicado: Radicado) -> Image.Image:
        expediente = catalogo.POR_RADICADO.get(radicado.valor)
        if expediente is None:
            raise RadicadoInexistente(f"No existe un proceso con el radicado {radicado}")
        return imagen_con_texto(expediente.codigo)


def escribir_csv(ruta: Path, filas: list[str]) -> Path:
    ruta.write_text("radicado,demandado\n" + "\n".join(filas) + "\n", encoding="utf-8")
    return ruta


def test_version() -> None:
    resultado = runner.invoke(cli.app, ["--version"])
    assert resultado.exit_code == 0
    assert "vigia-ocr 1.0.0" in resultado.output


def test_leer_radicados_omite_invalidos_y_duplicados(tmp_path: Path) -> None:
    archivo = escribir_csv(
        tmp_path / "r.csv",
        ["PCA-2026-00017,A", "no-es-radicado,B", "PCA-2026-00017,A", "PCA-2026-00023,C", ",D"],
    )
    assert [r.valor for r in cli.leer_radicados(archivo)] == ["PCA-2026-00017", "PCA-2026-00023"]


@pytest.mark.usefixtures("motores_falsos")
def test_consultar_lote_completo_y_repetirlo_es_idempotente(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(selenium_portal, "PortalSelenium", NavegadorFalso)
    archivo = escribir_csv(
        tmp_path / "lote.csv", [e.radicado + ",x" for e in catalogo.EXPEDIENTES[:3]]
    )

    primera = runner.invoke(cli.app, ["consultar", str(archivo), "--fecha-corte", "2026-11-12"])
    assert primera.exit_code == 0, primera.output
    assert primera.stdout.count(" guardado ") == 3
    assert "3/3 radicados con estado confirmado" in primera.stdout
    assert catalogo.EXPEDIENTES[0].codigo in primera.stdout

    segunda = runner.invoke(cli.app, ["consultar", str(archivo), "--fecha-corte", "2026-11-12"])
    assert segunda.exit_code == 0
    assert segunda.stdout.count("omitido_ya_existia") == 3


@pytest.mark.usefixtures("motores_falsos")
def test_consultar_devuelve_codigo_2_si_quedan_pendientes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class NavegadorIlegible(NavegadorFalso):
        def obtener_imagen_estado(self, radicado: Radicado) -> Image.Image:
            return imagen_con_texto("???")

    monkeypatch.setattr(selenium_portal, "PortalSelenium", NavegadorIlegible)
    archivo = escribir_csv(tmp_path / "lote.csv", ["PCA-2026-00017,x"])
    resultado = runner.invoke(cli.app, ["consultar", str(archivo)])
    assert resultado.exit_code == cli.CODIGO_PENDIENTES
    assert "sin_lectura_confiable" in resultado.output


@pytest.mark.usefixtures("motores_falsos")
def test_leer_imagenes(tmp_path: Path) -> None:
    ruta = tmp_path / "estado.png"
    Image.new("RGB", (10, 10)).save(ruta)
    resultado = runner.invoke(cli.app, ["leer", str(ruta)])
    assert resultado.exit_code == 0, resultado.output
    assert "SIN CONSENSO" in resultado.output  # el motor falso no ve metadatos en un PNG


def test_muestras(tmp_path: Path) -> None:
    resultado = runner.invoke(
        cli.app, ["muestras", "--cantidad", "3", "--salida", str(tmp_path / "m")]
    )
    assert resultado.exit_code == 0
    archivos = sorted(p.name for p in (tmp_path / "m").iterdir())
    assert len(archivos) == 3
    assert all(len(nombre.split("_")[1].removesuffix(".png")) == 8 for nombre in archivos)


def test_evaluar_con_motor_falso(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setitem(modulo_ocr.FABRICAS, "ddddocr", lambda: MotorGuion("ddddocr", ["x"]))
    salida = tmp_path / "docs" / "evaluacion.md"
    resultado = runner.invoke(
        cli.app,
        ["evaluar", "--cantidad", "10", "--motores", "ddddocr", "--salida", str(salida)],
    )
    assert resultado.exit_code == 0, resultado.output
    assert salida.exists()
    assert json.loads(salida.with_suffix(".json").read_text(encoding="utf-8"))["cantidad"] == 10


def test_evaluar_sin_motores_disponibles(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_disponible() -> MotorGuion:
        raise MotorNoDisponible("no")

    monkeypatch.setitem(modulo_ocr.FABRICAS, "ddddocr", no_disponible)
    resultado = runner.invoke(cli.app, ["evaluar", "--cantidad", "10", "--motores", "ddddocr"])
    assert resultado.exit_code == 1


def test_evaluar_motor_desconocido() -> None:
    resultado = runner.invoke(cli.app, ["evaluar", "--cantidad", "10", "--motores", "magia"])
    assert resultado.exit_code != 0


def test_db_crear(tmp_path: Path) -> None:
    resultado = runner.invoke(cli.app, ["db-crear"])
    assert resultado.exit_code == 0
    assert (tmp_path / "cli.db").exists()


@pytest.mark.usefixtures("motores_falsos")
def test_demo_web(tmp_path: Path) -> None:
    evaluacion = tmp_path / "ev.json"
    evaluacion.write_text(json.dumps({"cantidad": 1, "filas": []}), encoding="utf-8")
    resultado = runner.invoke(
        cli.app,
        ["demo-web", "--salida", str(tmp_path / "site"), "--cantidad", "2",
         "--motores", "ddddocr", "--evaluacion", str(evaluacion)],
    )  # fmt: skip
    assert resultado.exit_code == 0, resultado.output
    html = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert "/*__DATOS__*/" not in html
    assert '"cantidad": 1' in html
    # Imagen original + una por variante configurada (VIGIA_VARIANTES=original).
    assert len(list((tmp_path / "site" / "img").glob("caso00*.png"))) == 2
