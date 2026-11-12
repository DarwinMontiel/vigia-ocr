"""El banco de evaluación con un motor falso cuyo comportamiento se conoce de antemano.

Cada imagen falsa codifica su semilla en un píxel y se registra con su código; el motor falso
"lee" consultando ese registro y se equivoca a propósito con un patrón determinista, así cada
fila del informe se puede predecir.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from tests.conftest import MotorGuion, VarianteIdentidad, imagen_con_texto
from vigia_ocr.evaluacion import banco as modulo_banco
from vigia_ocr.evaluacion.banco import (
    BancoEvaluacion,
    FilaInforme,
    MotorMedido,
    escribir_informe,
    informe_a_markdown,
)
from vigia_ocr.sintetico.generador import Muestra, ParametrosRuido, generar_lote

REGISTRO: dict[bytes, tuple[str, int]] = {}


def _imagen_codificada(codigo: str, semilla: int) -> Image.Image:
    imagen = imagen_con_texto(codigo)
    # Píxel distinto por semilla: imágenes distintas tienen bytes distintos (cache del banco).
    imagen.putpixel((0, 7), (semilla % 256, (semilla >> 8) % 256, (semilla >> 16) % 256))
    REGISTRO[imagen.tobytes()] = (codigo, semilla)
    return imagen


def leer_registro(imagen: Image.Image) -> tuple[str, int]:
    return REGISTRO[imagen.convert("RGB").tobytes()]


def _render_falso(codigo: str, semilla: int, _p: ParametrosRuido | None = None) -> Image.Image:
    return _imagen_codificada(codigo, semilla)


def _lote_falso(cantidad: int, semilla: int, _p: ParametrosRuido | None = None) -> list[Muestra]:
    return [
        Muestra(m.codigo, m.semilla, _imagen_codificada(m.codigo, m.semilla))
        for m in generar_lote(cantidad, semilla)
    ]


@pytest.fixture(autouse=True)
def _imagenes_falsas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modulo_banco, "generar_lote", _lote_falso)
    monkeypatch.setattr(modulo_banco, "renderizar", _render_falso)


def lector_preciso(imagen: Image.Image) -> str:
    return leer_registro(imagen)[0]


def test_motor_medido_memoriza_lecturas() -> None:
    motor = MotorGuion("x", ["AP482133"])
    medido = MotorMedido(motor)
    imagen = imagen_con_texto("AP482133")
    assert medido.leer(imagen) == medido.leer(imagen.copy()) == "AP482133"
    assert motor.llamadas == 1
    assert medido.lecturas_reales == 1
    assert medido.ms_por_lectura >= 0


def test_banco_con_motor_perfecto() -> None:
    banco = BancoEvaluacion(
        [MotorGuion("perfecto", lector_preciso)],
        [VarianteIdentidad("v1"), VarianteIdentidad("v2")],
        cantidad=20,
        semilla=3,
    )
    informe = banco.ejecutar()
    assert [f.grupo for f in informe.filas] == [
        "1. Motor solo",
        "2. Preprocesado",
        "3. Votación por motor",
        "5. Producción",
    ]
    assert all(f.acierto == 1.0 for f in informe.filas)
    assert informe.motores == ["perfecto"]


def test_reintentos_de_imagen_suben_el_acierto() -> None:
    def ilegible_si_semilla_par(imagen: Image.Image) -> str:
        texto, semilla = leer_registro(imagen)
        return texto[:5] if semilla % 2 == 0 else texto

    banco = BancoEvaluacion(
        [MotorGuion("a", ilegible_si_semilla_par), MotorGuion("b", ilegible_si_semilla_par)],
        [VarianteIdentidad()],
        cantidad=40,
        semilla=11,
        max_imagenes=3,
    )
    informe = banco.ejecutar()
    por_grupo = {f.grupo: f for f in informe.filas}
    una_imagen = por_grupo["4. Votación entre motores"]
    produccion = por_grupo["5. Producción"]
    assert una_imagen.errores == 0
    assert 0 < una_imagen.acierto < 1
    assert produccion.acierto > una_imagen.acierto
    assert produccion.imagenes_promedio > 1
    # Ablación: una fila por motor quitado.
    assert [f.configuracion for f in informe.filas if f.grupo == "6. Ablación"] == [
        "Producción sin a",
        "Producción sin b",
    ]


def test_errores_silenciosos_y_sin_respuesta_se_cuentan_por_separado() -> None:
    def siempre_otro_codigo(_imagen: Image.Image) -> str:
        return "TE000000"  # válido, pero equivocado

    banco = BancoEvaluacion(
        [MotorGuion("terco", siempre_otro_codigo)], [VarianteIdentidad()], cantidad=10, semilla=1
    )
    cruda = banco.ejecutar().filas[0]
    assert cruda.errores + cruda.aciertos + cruda.sin_respuesta == 10
    assert cruda.error_silencioso > 0.5


def test_fila_vacia_no_divide_por_cero() -> None:
    fila = FilaInforme("x", "g", 0, 0, 0, 0)
    assert (fila.acierto, fila.error_silencioso, fila.tasa_sin_respuesta) == (0.0, 0.0, 0.0)


def test_requiere_motores() -> None:
    with pytest.raises(ValueError, match="al menos un motor"):
        BancoEvaluacion([], [VarianteIdentidad()])


def test_informe_markdown_y_json(tmp_path: Path) -> None:
    banco = BancoEvaluacion(
        [MotorGuion("perfecto", lector_preciso)],
        [VarianteIdentidad()],
        cantidad=10,
        semilla=5,
        motores_omitidos=["easyocr"],
    )
    informe = banco.ejecutar(progreso=lambda _t: None)
    destino = tmp_path / "docs" / "evaluacion.md"
    ruta_json = escribir_informe(informe, destino)

    markdown = destino.read_text(encoding="utf-8")
    assert "| 5. Producción |" in markdown
    assert "**100,0 %**" in markdown
    assert "omitidos (no instalados):** easyocr" in markdown
    assert markdown == informe_a_markdown(informe)

    datos = json.loads(ruta_json.read_text(encoding="utf-8"))
    assert datos["semilla"] == 5
    assert datos["filas"][-1]["acierto"] == 1.0
    assert "python" in datos["entorno"]
