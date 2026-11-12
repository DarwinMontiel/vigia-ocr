"""Reloj del sistema (implementa el puerto ``Reloj``)."""

from __future__ import annotations

import time
from datetime import UTC, datetime


class RelojSistema:
    def ahora(self) -> datetime:
        return datetime.now(UTC)

    def monotonico(self) -> float:
        return time.monotonic()
