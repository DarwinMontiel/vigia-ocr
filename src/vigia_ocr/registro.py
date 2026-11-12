"""Logs estructurados con structlog: legibles en consola, JSON en servidores.

Los mensajes van en español y los datos van en campos (``radicado=...``), no interpolados en
el texto: así se pueden filtrar en cualquier agregador de logs.
"""

from __future__ import annotations

import logging
import sys
from typing import Literal

import structlog


class _StderrActual:
    """Resuelve ``sys.stderr`` en cada escritura (no al configurar): sobrevive a que alguien
    reemplace el flujo, como hacen los ejecutores de pruebas y algunos servicios de Windows."""

    def write(self, texto: str) -> int:
        return sys.stderr.write(texto)

    def flush(self) -> None:
        sys.stderr.flush()


def configurar_registro(
    formato: Literal["consola", "json"] = "consola", nivel: str = "INFO"
) -> None:
    nivel_numerico = logging.getLevelNamesMapping()[nivel]
    procesadores: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=False, key="momento"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderizador: structlog.typing.Processor
    if formato == "json":
        procesadores.append(structlog.processors.EventRenamer("mensaje"))
        renderizador = structlog.processors.JSONRenderer(ensure_ascii=False)
    else:
        renderizador = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    structlog.configure(
        processors=[*procesadores, renderizador],
        wrapper_class=structlog.make_filtering_bound_logger(nivel_numerico),
        logger_factory=structlog.PrintLoggerFactory(file=_StderrActual()),  # type: ignore[arg-type]
        cache_logger_on_first_use=False,
    )
