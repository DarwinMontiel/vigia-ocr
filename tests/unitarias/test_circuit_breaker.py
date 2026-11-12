from __future__ import annotations

import pytest

from tests.conftest import RelojFalso
from vigia_ocr.aplicacion.circuit_breaker import CircuitBreaker, EstadoCircuito
from vigia_ocr.dominio.errores import CircuitoAbierto, PortalNoDisponible, RadicadoInexistente


def fallar() -> None:
    raise PortalNoDisponible("503")


def fallos(breaker: CircuitBreaker, veces: int) -> None:
    for _ in range(veces):
        with pytest.raises(PortalNoDisponible):
            breaker.llamar(fallar)


def test_se_abre_tras_el_umbral_de_fallos_seguidos(reloj: RelojFalso) -> None:
    breaker = CircuitBreaker(reloj, umbral_fallos=3, enfriamiento_s=30)
    fallos(breaker, 2)
    assert breaker.estado is EstadoCircuito.CERRADO
    fallos(breaker, 1)
    assert breaker.estado is EstadoCircuito.ABIERTO


def test_abierto_rechaza_sin_llamar_al_portal(reloj: RelojFalso) -> None:
    breaker = CircuitBreaker(reloj, umbral_fallos=1, enfriamiento_s=30)
    fallos(breaker, 1)
    llamadas: list[int] = []
    reloj.avanzar(10)
    with pytest.raises(CircuitoAbierto) as error:
        breaker.llamar(lambda: llamadas.append(1))
    assert llamadas == []
    assert error.value.segundos_restantes == pytest.approx(20)
    assert "Circuito abierto" in str(error.value)


def test_semiabierto_tras_enfriar_y_se_cierra_si_la_prueba_funciona(reloj: RelojFalso) -> None:
    breaker = CircuitBreaker(reloj, umbral_fallos=1, enfriamiento_s=30)
    fallos(breaker, 1)
    reloj.avanzar(30)
    assert breaker.estado is EstadoCircuito.SEMIABIERTO
    assert breaker.llamar(lambda: "ok") == "ok"
    assert breaker.estado is EstadoCircuito.CERRADO


def test_semiabierto_vuelve_a_abrirse_con_un_solo_fallo(reloj: RelojFalso) -> None:
    breaker = CircuitBreaker(reloj, umbral_fallos=5, enfriamiento_s=30)
    fallos(breaker, 5)
    reloj.avanzar(31)
    fallos(breaker, 1)
    assert breaker.estado is EstadoCircuito.ABIERTO


def test_un_exito_reinicia_el_conteo(reloj: RelojFalso) -> None:
    breaker = CircuitBreaker(reloj, umbral_fallos=3)
    fallos(breaker, 2)
    breaker.llamar(lambda: None)
    fallos(breaker, 2)
    assert breaker.estado is EstadoCircuito.CERRADO


def test_errores_de_negocio_no_abren_el_circuito(reloj: RelojFalso) -> None:
    breaker = CircuitBreaker(reloj, umbral_fallos=1)

    def inexistente() -> None:
        raise RadicadoInexistente("no existe")

    for _ in range(3):
        with pytest.raises(RadicadoInexistente):
            breaker.llamar(inexistente)
    assert breaker.estado is EstadoCircuito.CERRADO


def test_umbral_invalido(reloj: RelojFalso) -> None:
    with pytest.raises(ValueError, match="umbral"):
        CircuitBreaker(reloj, umbral_fallos=0)
