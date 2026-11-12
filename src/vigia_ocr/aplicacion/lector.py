"""Cadena OCR: preprocesa la imagen en varias variantes, la lee con varios motores y vota."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import structlog
from PIL import Image

from vigia_ocr.dominio.codigo import es_codigo_valido
from vigia_ocr.dominio.errores import ErrorDeSistema
from vigia_ocr.dominio.modelos import LecturaMotor, Veredicto
from vigia_ocr.dominio.normalizacion import normalizar
from vigia_ocr.dominio.votacion import votar
from vigia_ocr.puertos import MotorOCR, Preprocesador

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Combinacion:
    """Un motor aplicado a una variante de preprocesado, con su peso en la votación."""

    motor: MotorOCR
    variante: Preprocesador
    peso: float = 1.0


class LectorConsenso:
    """Lee una imagen con todas las combinaciones (motor × variante) y decide por votación.

    Con ``parada_temprana`` deja de leer en cuanto ``min_acuerdo`` lecturas válidas coinciden
    y no hay otro código válido compitiendo: en la mayoría de imágenes basta con los motores
    rápidos y nunca se llega al lento.
    """

    def __init__(
        self,
        combinaciones: Sequence[Combinacion],
        *,
        min_acuerdo: int = 2,
        parada_temprana: bool = True,
    ) -> None:
        if not combinaciones:
            raise ValueError("Se necesita al menos una combinación motor × variante")
        self._combinaciones = tuple(combinaciones)
        self._min_acuerdo = min_acuerdo
        self._parada_temprana = parada_temprana

    @classmethod
    def desde_motores(
        cls,
        motores: Sequence[MotorOCR],
        variantes: Sequence[Preprocesador],
        *,
        pesos: Mapping[str, float] | None = None,
        min_acuerdo: int = 2,
        parada_temprana: bool = True,
    ) -> LectorConsenso:
        """Producto cartesiano ordenado por variante: primero todas las lecturas de la variante
        más útil, para que la parada temprana se active cuanto antes."""
        pesos = pesos or {}
        combinaciones = [
            Combinacion(motor, variante, pesos.get(motor.nombre, 1.0))
            for variante in variantes
            for motor in motores
        ]
        return cls(combinaciones, min_acuerdo=min_acuerdo, parada_temprana=parada_temprana)

    def leer(self, imagen: Image.Image) -> Veredicto:
        lecturas: list[LecturaMotor] = []
        cache_variantes: dict[str, Image.Image] = {}
        for combinacion in self._combinaciones:
            variante = combinacion.variante
            if variante.nombre not in cache_variantes:
                cache_variantes[variante.nombre] = variante.aplicar(imagen)
            try:
                crudo = combinacion.motor.leer(cache_variantes[variante.nombre])
            except ErrorDeSistema:
                raise
            except Exception as error:  # un motor que falla no debe tumbar la lectura
                log.warning(
                    "Un motor OCR falló; se continúa con los demás",
                    motor=combinacion.motor.nombre,
                    variante=variante.nombre,
                    error=repr(error),
                )
                continue
            normalizado = normalizar(crudo)
            lecturas.append(
                LecturaMotor(
                    motor=combinacion.motor.nombre,
                    variante=variante.nombre,
                    texto_crudo=crudo,
                    texto_normalizado=normalizado,
                    valido=es_codigo_valido(normalizado),
                    peso=combinacion.peso,
                )
            )
            if self._parada_temprana and self._hay_acuerdo_suficiente(lecturas):
                break
        return votar(lecturas, min_acuerdo=self._min_acuerdo)

    def _hay_acuerdo_suficiente(self, lecturas: Sequence[LecturaMotor]) -> bool:
        validas = [x.texto_normalizado for x in lecturas if x.valido]
        distintas = set(validas)
        return len(distintas) == 1 and len(validas) >= self._min_acuerdo
