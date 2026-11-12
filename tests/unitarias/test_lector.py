from __future__ import annotations

import pytest
from PIL import Image

from tests.conftest import MotorGuion, VarianteIdentidad, codigo_ejemplo, imagen_con_texto
from vigia_ocr.aplicacion.lector import Combinacion, LectorConsenso
from vigia_ocr.dominio.errores import MotorNoDisponible
from vigia_ocr.dominio.modelos import MetodoVeredicto

BUENO = codigo_ejemplo()
IMAGEN = imagen_con_texto(BUENO)


def test_requiere_al_menos_una_combinacion() -> None:
    with pytest.raises(ValueError, match="al menos una"):
        LectorConsenso([])


def test_parada_temprana_ahorra_los_motores_lentos() -> None:
    rapido = MotorGuion("rapido", [BUENO])
    lento = MotorGuion("lento", [BUENO])
    lector = LectorConsenso.desde_motores(
        [rapido, lento], [VarianteIdentidad("a"), VarianteIdentidad("b")], min_acuerdo=2
    )
    veredicto = lector.leer(IMAGEN)
    assert veredicto.codigo == BUENO
    # Orden: (a, rapido), (a, lento) → ya hay dos lecturas válidas iguales: se detiene.
    assert (rapido.llamadas, lento.llamadas) == (1, 1)
    assert len(veredicto.lecturas) == 2


def test_sin_parada_temprana_lee_todas_las_combinaciones() -> None:
    motores = [MotorGuion("a", [BUENO]), MotorGuion("b", [BUENO])]
    variantes = [VarianteIdentidad("x"), VarianteIdentidad("y"), VarianteIdentidad("z")]
    lector = LectorConsenso.desde_motores(motores, variantes, parada_temprana=False)
    veredicto = lector.leer(IMAGEN)
    assert len(veredicto.lecturas) == 6
    assert veredicto.metodo is MetodoVeredicto.UNANIME


def test_cada_variante_se_aplica_una_sola_vez() -> None:
    variante = VarianteIdentidad("unica")
    motores = [MotorGuion("a", ["x"]), MotorGuion("b", ["y"]), MotorGuion("c", ["z"])]
    LectorConsenso.desde_motores(motores, [variante]).leer(IMAGEN)
    assert variante.aplicaciones == 1


def test_un_motor_que_explota_no_tumba_la_lectura() -> None:
    def explotar(_imagen: Image.Image) -> str:
        raise RuntimeError("modelo corrupto")

    lector = LectorConsenso.desde_motores(
        [MotorGuion("roto", explotar), MotorGuion("sano", [BUENO])],
        [VarianteIdentidad("a"), VarianteIdentidad("b")],
    )
    veredicto = lector.leer(IMAGEN)
    assert veredicto.codigo == BUENO
    assert {x.motor for x in veredicto.lecturas} == {"sano"}


def test_motor_no_disponible_si_se_propaga() -> None:
    def no_disponible(_imagen: Image.Image) -> str:
        raise MotorNoDisponible("sin binario")

    lector = LectorConsenso.desde_motores([MotorGuion("x", no_disponible)], [VarianteIdentidad()])
    with pytest.raises(MotorNoDisponible):
        lector.leer(IMAGEN)


def test_normaliza_y_marca_validez_de_cada_lectura() -> None:
    lector = LectorConsenso(
        [
            Combinacion(MotorGuion("a", [BUENO.lower()]), VarianteIdentidad("v1")),
            Combinacion(MotorGuion("b", ["basura"]), VarianteIdentidad("v2"), peso=0.5),
        ],
        parada_temprana=False,
        min_acuerdo=1,
    )
    veredicto = lector.leer(IMAGEN)
    primera, segunda = veredicto.lecturas
    assert (primera.texto_normalizado, primera.valido) == (BUENO, True)
    assert (segunda.valido, segunda.peso) == (False, 0.5)
    assert veredicto.codigo == BUENO


def test_pesos_por_motor() -> None:
    lector = LectorConsenso.desde_motores(
        [MotorGuion("a", ["x"])], [VarianteIdentidad()], pesos={"a": 3.0}
    )
    assert lector.leer(IMAGEN).lecturas[0].peso == 3.0
