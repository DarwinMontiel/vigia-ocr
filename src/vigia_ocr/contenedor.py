"""Raíz de composición: el único lugar que conoce a la vez el núcleo y los adaptadores.

Aquí se decide qué implementación concreta recibe cada puerto. Las pruebas arman el mismo
grafo con dobles; producción lo arma con Selenium, SQL Server y motores reales.
"""

from __future__ import annotations

from dataclasses import dataclass

from vigia_ocr.adaptadores.ocr import crear_motores
from vigia_ocr.adaptadores.persistencia.sql import RepositorioSQL, crear_esquema, crear_motor_bd
from vigia_ocr.adaptadores.preprocesado import variantes_por_nombre
from vigia_ocr.adaptadores.reloj import RelojSistema
from vigia_ocr.aplicacion.circuit_breaker import CircuitBreaker
from vigia_ocr.aplicacion.consultar import ServicioConsulta
from vigia_ocr.aplicacion.lector import LectorConsenso
from vigia_ocr.config import Configuracion
from vigia_ocr.puertos import PortalConsultas, Reloj, RepositorioResultados


def crear_lector(config: Configuracion) -> LectorConsenso:
    motores = crear_motores(
        config.motores, omitir_no_disponibles=config.omitir_motores_no_disponibles
    )
    return LectorConsenso.desde_motores(
        motores, variantes_por_nombre(config.variantes), min_acuerdo=config.min_acuerdo
    )


@dataclass(frozen=True, slots=True)
class Dependencias:
    portal: PortalConsultas
    repositorio: RepositorioResultados
    lector: LectorConsenso
    reloj: Reloj


def crear_servicio(config: Configuracion, dependencias: Dependencias) -> ServicioConsulta:
    breaker = CircuitBreaker(
        dependencias.reloj,
        umbral_fallos=config.breaker_umbral_fallos,
        enfriamiento_s=config.breaker_enfriamiento_s,
    )
    return ServicioConsulta(
        dependencias.portal,
        dependencias.lector,
        dependencias.repositorio,
        breaker,
        dependencias.reloj,
        max_imagenes=config.max_imagenes,
        confianza_minima=config.confianza_minima,
    )


def crear_repositorio_sql(config: Configuracion) -> RepositorioSQL:
    """En SQLite crea las tablas si faltan; en SQL Server el esquema lo gestiona el DDL."""
    motor = crear_motor_bd(config.base_datos_url)
    if motor.dialect.name == "sqlite":
        crear_esquema(motor)
    return RepositorioSQL(motor)


__all__ = [
    "Dependencias",
    "RelojSistema",
    "crear_lector",
    "crear_repositorio_sql",
    "crear_servicio",
]
