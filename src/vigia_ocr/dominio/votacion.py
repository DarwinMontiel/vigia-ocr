"""Votación ponderada entre lecturas de varios motores y variantes de preprocesado.

Reglas, en orden:

1. **Mayoría entre lecturas válidas.** Solo votan las lecturas que pasan el patrón y el dígito
   de verificación. Gana el código con más peso acumulado, siempre que reúna al menos
   ``min_acuerdo`` lecturas y no empate con otro código válido.
2. **Votación por carácter.** Si no hay mayoría ni códigos válidos en conflicto, se vota
   posición por posición entre las lecturas de longitud correcta. El resultado se acepta solo si el
   dígito de verificación cuadra (el DV actúa como árbitro independiente).
3. **Sin consenso.** Se devuelve ``codigo=None`` y el caso de uso pide una imagen nueva al
   portal. Preferimos no responder a responder mal: un estado equivocado en la base de datos
   es peor que un reintento.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence

from vigia_ocr.dominio.codigo import LONGITUD, es_codigo_valido
from vigia_ocr.dominio.modelos import LecturaMotor, MetodoVeredicto, Veredicto


def votar(lecturas: Sequence[LecturaMotor], *, min_acuerdo: int = 2) -> Veredicto:
    """Decide el código de una imagen a partir de todas sus lecturas."""
    if min_acuerdo < 1:
        raise ValueError("min_acuerdo debe ser al menos 1")
    tupla = tuple(lecturas)
    peso_total = sum(lectura.peso for lectura in tupla)
    if not tupla or peso_total <= 0:
        return Veredicto(None, MetodoVeredicto.SIN_CONSENSO, 0.0, tupla)

    por_mayoria = _mayoria_valida(tupla, peso_total, min_acuerdo)
    if por_mayoria is not None:
        return por_mayoria

    codigos_validos = {x.texto_normalizado for x in tupla if x.valido}
    if len(codigos_validos) > 1:
        # Hay códigos válidos en conflicto: mezclar sus caracteres sería inventar uno.
        return Veredicto(None, MetodoVeredicto.SIN_CONSENSO, 0.0, tupla)

    por_caracter = _votacion_por_caracter(tupla, peso_total)
    if por_caracter is not None:
        return por_caracter

    return Veredicto(None, MetodoVeredicto.SIN_CONSENSO, 0.0, tupla)


def _mayoria_valida(
    lecturas: tuple[LecturaMotor, ...], peso_total: float, min_acuerdo: int
) -> Veredicto | None:
    pesos: defaultdict[str, float] = defaultdict(float)
    conteo: Counter[str] = Counter()
    for lectura in lecturas:
        if lectura.valido:
            pesos[lectura.texto_normalizado] += lectura.peso
            conteo[lectura.texto_normalizado] += 1
    if not pesos:
        return None

    ranking = sorted(pesos.items(), key=lambda par: par[1], reverse=True)
    ganador, peso_ganador = ranking[0]
    if len(ranking) > 1 and ranking[1][1] == peso_ganador:
        return None  # empate entre dos códigos válidos: no hay forma honesta de elegir
    if conteo[ganador] < min(min_acuerdo, len(lecturas)):
        return None

    unanime = conteo[ganador] == len(lecturas)
    metodo = MetodoVeredicto.UNANIME if unanime else MetodoVeredicto.MAYORIA
    return Veredicto(ganador, metodo, round(peso_ganador / peso_total, 4), lecturas)


def _votacion_por_caracter(
    lecturas: tuple[LecturaMotor, ...], peso_total: float
) -> Veredicto | None:
    completas = [x for x in lecturas if len(x.texto_normalizado) == LONGITUD]
    if len(completas) < 2:
        return None

    caracteres: list[str] = []
    confianzas: list[float] = []
    for posicion in range(LONGITUD):
        pesos: defaultdict[str, float] = defaultdict(float)
        for lectura in completas:
            pesos[lectura.texto_normalizado[posicion]] += lectura.peso
        caracter, peso = max(pesos.items(), key=lambda par: par[1])
        caracteres.append(caracter)
        confianzas.append(peso / peso_total)

    candidato = "".join(caracteres)
    if not es_codigo_valido(candidato):
        return None
    # La confianza de una cadena es la de su carácter más débil.
    return Veredicto(candidato, MetodoVeredicto.POR_CARACTER, round(min(confianzas), 4), lecturas)
