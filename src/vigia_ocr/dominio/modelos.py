"""Entidades y objetos de valor del dominio."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Final

from vigia_ocr.dominio.codigo import EstadoObligacion

PATRON_RADICADO: Final[re.Pattern[str]] = re.compile(r"^PCA-\d{4}-\d{5}$")


@dataclass(frozen=True, slots=True)
class Radicado:
    """Número de radicado del expediente en el juzgado ficticio de Puerto Candela."""

    valor: str

    def __post_init__(self) -> None:
        if not PATRON_RADICADO.fullmatch(self.valor):
            raise ValueError(
                f"Radicado inválido {self.valor!r}: se espera el formato PCA-AAAA-NNNNN"
            )

    def __str__(self) -> str:
        return self.valor


@dataclass(frozen=True, slots=True)
class LecturaMotor:
    """Lo que un motor OCR leyó sobre una variante preprocesada de la imagen."""

    motor: str
    variante: str
    texto_crudo: str
    texto_normalizado: str
    valido: bool
    peso: float = 1.0


class MetodoVeredicto(StrEnum):
    UNANIME = "unanime"
    MAYORIA = "mayoria"
    POR_CARACTER = "por_caracter"
    SIN_CONSENSO = "sin_consenso"


@dataclass(frozen=True, slots=True)
class Veredicto:
    """Resultado de la votación entre todas las lecturas de una imagen."""

    codigo: str | None
    metodo: MetodoVeredicto
    confianza: float
    lecturas: tuple[LecturaMotor, ...]

    @property
    def aceptado(self) -> bool:
        return self.codigo is not None

    @property
    def estado(self) -> EstadoObligacion | None:
        return EstadoObligacion(self.codigo[:2]) if self.codigo else None


@dataclass(frozen=True, slots=True)
class ResultadoConsulta:
    """Estado leído y validado de un radicado para una fecha de corte. Es lo que se persiste."""

    radicado: Radicado
    fecha_corte: date
    codigo: str
    estado: EstadoObligacion
    confianza: float
    metodo: MetodoVeredicto
    imagenes_consultadas: int
    consultado_en: datetime
    lecturas: tuple[LecturaMotor, ...] = field(default=(), compare=False)

    @property
    def clave_idempotencia(self) -> str:
        return clave_idempotencia(self.radicado, self.fecha_corte)


def clave_idempotencia(radicado: Radicado, fecha_corte: date) -> str:
    """Un radicado se consulta una sola vez por fecha de corte, aunque el lote se repita."""
    return f"{radicado.valor}@{fecha_corte.isoformat()}"


class Desenlace(StrEnum):
    """Cómo terminó el procesamiento de un radicado dentro de un lote."""

    GUARDADO = "guardado"
    OMITIDO_YA_EXISTIA = "omitido_ya_existia"
    SIN_LECTURA_CONFIABLE = "sin_lectura_confiable"
    RADICADO_INEXISTENTE = "radicado_inexistente"
    PORTAL_NO_DISPONIBLE = "portal_no_disponible"
    CIRCUITO_ABIERTO = "circuito_abierto"


@dataclass(frozen=True, slots=True)
class ResultadoRadicado:
    radicado: Radicado
    desenlace: Desenlace
    detalle: str = ""
    resultado: ResultadoConsulta | None = None


@dataclass(slots=True)
class ResumenLote:
    """Totales de un lote, para el log final y el código de salida del CLI."""

    resultados: list[ResultadoRadicado] = field(default_factory=list)

    def contar(self, desenlace: Desenlace) -> int:
        return sum(1 for r in self.resultados if r.desenlace is desenlace)

    @property
    def total(self) -> int:
        return len(self.resultados)

    @property
    def exitosos(self) -> int:
        return self.contar(Desenlace.GUARDADO) + self.contar(Desenlace.OMITIDO_YA_EXISTIA)

    @property
    def pendientes(self) -> list[Radicado]:
        """Radicados que conviene reintentar en la próxima corrida."""
        reintentables = {
            Desenlace.SIN_LECTURA_CONFIABLE,
            Desenlace.PORTAL_NO_DISPONIBLE,
            Desenlace.CIRCUITO_ABIERTO,
        }
        return [r.radicado for r in self.resultados if r.desenlace in reintentables]
