"""Repositorio en memoria: mismo contrato que el de SQL, útil en pruebas y en la demo."""

from __future__ import annotations

from datetime import date
from threading import Lock

from vigia_ocr.dominio.modelos import Radicado, ResultadoConsulta, clave_idempotencia


class RepositorioEnMemoria:
    def __init__(self) -> None:
        self._datos: dict[str, ResultadoConsulta] = {}
        self._candado = Lock()

    def obtener(self, radicado: Radicado, fecha_corte: date) -> ResultadoConsulta | None:
        return self._datos.get(clave_idempotencia(radicado, fecha_corte))

    def guardar(self, resultado: ResultadoConsulta) -> bool:
        with self._candado:
            if resultado.clave_idempotencia in self._datos:
                return False
            self._datos[resultado.clave_idempotencia] = resultado
            return True

    def todos(self) -> list[ResultadoConsulta]:
        return list(self._datos.values())
