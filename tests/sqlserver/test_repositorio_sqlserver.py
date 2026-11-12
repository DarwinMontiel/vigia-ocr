"""Repositorio contra un SQL Server real (``pytest -m sqlserver``).

Necesita ``VIGIA_PRUEBAS_SQLSERVER_URL`` (p. ej. el contenedor de ``docker compose``) y el
ODBC Driver 18. Aplica ``sql/001_esquema.sql`` tal como lo haría un DBA.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from vigia_ocr.adaptadores.persistencia.sql import RepositorioSQL, crear_motor_bd
from vigia_ocr.dominio.codigo import EstadoObligacion, construir_codigo
from vigia_ocr.dominio.modelos import LecturaMotor, MetodoVeredicto, Radicado, ResultadoConsulta

pytestmark = pytest.mark.sqlserver
SCRIPT = Path(__file__).parents[2] / "sql" / "001_esquema.sql"


@pytest.fixture(scope="module")
def motor() -> Iterator[Engine]:
    url = os.environ.get("VIGIA_PRUEBAS_SQLSERVER_URL")
    if not url:
        pytest.skip("Define VIGIA_PRUEBAS_SQLSERVER_URL para probar contra SQL Server")
    motor = crear_motor_bd(url)
    lotes = re.split(r"^\s*GO\s*$", SCRIPT.read_text("utf-8"), flags=re.M)
    with motor.begin() as conexion:
        conexion.execute(text("DROP VIEW IF EXISTS dbo.vigia_ultimo_estado"))
        conexion.execute(text("DROP TABLE IF EXISTS dbo.vigia_lecturas"))
        conexion.execute(text("DROP TABLE IF EXISTS dbo.vigia_resultados"))
    for _ in range(2):  # dos veces: el script debe ser idempotente
        for lote in lotes:
            if lote.strip():
                with motor.begin() as conexion:
                    conexion.exec_driver_sql(lote)
    yield motor
    motor.dispose()


def resultado(radicado: str, codigo: str) -> ResultadoConsulta:
    return ResultadoConsulta(
        radicado=Radicado(radicado),
        fecha_corte=date(2026, 11, 12),
        codigo=codigo,
        estado=EstadoObligacion(codigo[:2]),
        confianza=0.93,
        metodo=MetodoVeredicto.MAYORIA,
        imagenes_consultadas=1,
        consultado_en=datetime(2026, 11, 12, 6, 0, 1, 500000),
        lecturas=(LecturaMotor("ddddocr", "otsu_x2", codigo, codigo, True, 1.0),),
    )


def test_ida_y_vuelta_e_idempotencia(motor: Engine) -> None:
    repo = RepositorioSQL(motor)
    original = resultado("PCA-2026-00017", construir_codigo(EstadoObligacion.EMBARGO, "10974"))
    assert repo.guardar(original) is True
    assert repo.guardar(original) is False
    assert repo.obtener(original.radicado, original.fecha_corte) == original


def test_restricciones_del_ddl(motor: Engine) -> None:
    with pytest.raises(IntegrityError), motor.begin() as conexion:
        conexion.execute(
            text(
                "INSERT INTO dbo.vigia_resultados (radicado, fecha_corte, codigo, estado, "
                "confianza, metodo, imagenes_consultadas, consultado_en) VALUES "
                "('PCA-2026-00099', '2026-11-12', 'XX000000', 'XX', 0.5, 'mayoria', 1, "
                "SYSDATETIME())"
            )
        )


def test_vista_de_ultimo_estado(motor: Engine) -> None:
    repo = RepositorioSQL(motor)
    repo.guardar(resultado("PCA-2026-00023", construir_codigo(EstadoObligacion.ACTIVA, "77120")))
    with motor.connect() as conexion:
        filas = conexion.execute(
            text("SELECT estado FROM dbo.vigia_ultimo_estado WHERE radicado = 'PCA-2026-00023'")
        ).all()
    assert [f.estado for f in filas] == ["AC"]
