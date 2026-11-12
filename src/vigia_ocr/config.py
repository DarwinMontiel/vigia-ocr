"""Configuración por variables de entorno (prefijo ``VIGIA_``) o archivo ``.env``."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from vigia_ocr.adaptadores.ocr import FABRICAS
from vigia_ocr.adaptadores.preprocesado import CATALOGO


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VIGIA_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    portal_url: str = "http://127.0.0.1:8000"
    base_datos_url: str = Field(
        default="sqlite:///vigia.db",
        description="SQLAlchemy URL. SQL Server: mssql+pyodbc://usuario:clave@host/bd?driver=...",
    )

    motores: Annotated[list[str], NoDecode] = ["ddddocr", "tesseract", "easyocr"]
    omitir_motores_no_disponibles: bool = True
    variantes: Annotated[list[str], NoDecode] = list(CATALOGO)
    min_acuerdo: int = Field(default=2, ge=1)
    max_imagenes: int = Field(default=3, ge=1, le=10)
    confianza_minima: float = Field(default=0.0, ge=0.0, le=1.0)

    breaker_umbral_fallos: int = Field(default=3, ge=1)
    breaker_enfriamiento_s: float = Field(default=30.0, gt=0)

    navegador_headless: bool = True
    navegador_binario: str | None = Field(
        default=None, description="Ruta de Chrome/Chromium si no es la instalación estándar."
    )
    chromedriver: str | None = Field(
        default=None, description="Ruta de chromedriver. Si falta, Selenium Manager lo resuelve."
    )
    navegador_espera_s: float = Field(default=10.0, gt=0)

    log_formato: Literal["consola", "json"] = "consola"
    log_nivel: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @field_validator("motores", "variantes", mode="before")
    @classmethod
    def _separar_por_comas(cls, valor: object) -> object:
        if isinstance(valor, str):
            return [parte.strip() for parte in valor.split(",") if parte.strip()]
        return valor

    @field_validator("motores")
    @classmethod
    def _motores_conocidos(cls, valor: list[str]) -> list[str]:
        desconocidos = [m for m in valor if m not in FABRICAS]
        if desconocidos:
            raise ValueError(f"Motores desconocidos: {', '.join(desconocidos)}")
        return valor

    @field_validator("variantes")
    @classmethod
    def _variantes_conocidas(cls, valor: list[str]) -> list[str]:
        desconocidas = [v for v in valor if v not in CATALOGO]
        if desconocidas:
            raise ValueError(f"Variantes desconocidas: {', '.join(desconocidas)}")
        return valor


@lru_cache(maxsize=1)
def obtener_configuracion() -> Configuracion:
    return Configuracion()
