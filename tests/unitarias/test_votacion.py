from __future__ import annotations

import pytest

from tests.conftest import codigo_ejemplo
from vigia_ocr.dominio.codigo import es_codigo_valido
from vigia_ocr.dominio.modelos import LecturaMotor, MetodoVeredicto
from vigia_ocr.dominio.normalizacion import normalizar
from vigia_ocr.dominio.votacion import votar

BUENO = codigo_ejemplo("48213")  # AP482133
OTRO_VALIDO = codigo_ejemplo("10974")


def lectura(texto: str, motor: str = "m", peso: float = 1.0) -> LecturaMotor:
    normalizado = normalizar(texto)
    return LecturaMotor(motor, "v", texto, normalizado, es_codigo_valido(normalizado), peso)


def test_sin_lecturas_no_hay_consenso() -> None:
    veredicto = votar([])
    assert veredicto.codigo is None
    assert veredicto.metodo is MetodoVeredicto.SIN_CONSENSO
    assert not veredicto.aceptado
    assert veredicto.estado is None


def test_unanimidad() -> None:
    veredicto = votar([lectura(BUENO), lectura(BUENO), lectura(BUENO)])
    assert veredicto.codigo == BUENO
    assert veredicto.metodo is MetodoVeredicto.UNANIME
    assert veredicto.confianza == 1.0
    assert veredicto.estado is not None


def test_mayoria_ignora_lecturas_invalidas() -> None:
    veredicto = votar([lectura(BUENO), lectura("AP4821"), lectura(BUENO), lectura("XX000000")])
    assert veredicto.codigo == BUENO
    assert veredicto.metodo is MetodoVeredicto.MAYORIA
    assert veredicto.confianza == 0.5


def test_una_sola_lectura_valida_no_alcanza_el_acuerdo_minimo() -> None:
    veredicto = votar([lectura(BUENO), lectura("AP4821"), lectura("ZZ")], min_acuerdo=2)
    assert veredicto.codigo is None


def test_con_una_sola_lectura_basta_ella_misma() -> None:
    """Un motor solo, sin variantes: el acuerdo mínimo se limita al número de lecturas."""
    assert votar([lectura(BUENO)], min_acuerdo=2).codigo == BUENO


def test_empate_entre_codigos_validos_no_elige() -> None:
    veredicto = votar([lectura(BUENO), lectura(BUENO), lectura(OTRO_VALIDO), lectura(OTRO_VALIDO)])
    assert veredicto.codigo is None


def test_los_pesos_rompen_la_igualdad_de_votos() -> None:
    veredicto = votar(
        [
            lectura(BUENO, "fuerte", 2.0),
            lectura(BUENO, "fuerte", 2.0),
            lectura(OTRO_VALIDO, "debil", 1.0),
            lectura(OTRO_VALIDO, "debil", 1.0),
        ]
    )
    assert veredicto.codigo == BUENO
    assert veredicto.confianza == pytest.approx(4 / 6, abs=1e-4)


def test_votacion_por_caracter_cuando_ninguna_lectura_completa_es_valida() -> None:
    # Cada lectura tiene un error distinto; posición a posición gana el carácter correcto.
    lecturas = [lectura("AP482137"), lectura("AP482933"), lectura("AP412133")]
    assert not any(x.valido for x in lecturas)
    veredicto = votar(lecturas)
    assert veredicto.codigo == BUENO
    assert veredicto.metodo is MetodoVeredicto.POR_CARACTER
    assert veredicto.confianza == pytest.approx(2 / 3, abs=1e-4)


def test_votacion_por_caracter_descarta_si_el_dv_no_cuadra() -> None:
    veredicto = votar([lectura("AP482137"), lectura("AP482137"), lectura("AP412133")])
    assert veredicto.codigo is None


def test_con_codigos_validos_en_conflicto_no_se_vota_por_caracter() -> None:
    """Si dos códigos válidos distintos compiten, mezclar sus caracteres sería inventar."""
    veredicto = votar([lectura(BUENO), lectura(OTRO_VALIDO), lectura("AP482137")])
    assert veredicto.codigo is None


def test_votacion_por_caracter_necesita_dos_lecturas_completas() -> None:
    assert votar([lectura("AP482137"), lectura("AP48")]).codigo is None


def test_min_acuerdo_invalido() -> None:
    with pytest.raises(ValueError, match="min_acuerdo"):
        votar([lectura(BUENO)], min_acuerdo=0)


def test_peso_total_cero() -> None:
    assert votar([lectura(BUENO, peso=0.0)]).codigo is None
