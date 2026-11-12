"""El mismo contrato se prueba contra el repositorio en memoria y contra SQLite (SQLAlchemy)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy.dialects import mssql
from sqlalchemy.schema import CreateTable

from tests.conftest import FECHA_CORTE, codigo_ejemplo
from vigia_ocr.adaptadores.persistencia.memoria import RepositorioEnMemoria
from vigia_ocr.adaptadores.persistencia.sql import (
    Base,
    FilaResultado,
    RepositorioSQL,
    crear_esquema,
    crear_motor_bd,
)
from vigia_ocr.dominio.codigo import EstadoObligacion
from vigia_ocr.dominio.modelos import LecturaMotor, MetodoVeredicto, Radicado, ResultadoConsulta
from vigia_ocr.puertos import RepositorioResultados

RADICADO = Radicado("PCA-2026-00017")


def resultado(
    codigo: str | None = None, fecha: date = FECHA_CORTE, radicado: Radicado = RADICADO
) -> ResultadoConsulta:
    codigo = codigo or codigo_ejemplo()
    return ResultadoConsulta(
        radicado=radicado,
        fecha_corte=fecha,
        codigo=codigo,
        estado=EstadoObligacion(codigo[:2]),
        confianza=0.8,
        metodo=MetodoVeredicto.MAYORIA,
        imagenes_consultadas=2,
        consultado_en=datetime(2026, 11, 12, 6, 0, 5),
        lecturas=(
            LecturaMotor("ddddocr", "otsu_x2", codigo.lower(), codigo, True, 1.0),
            LecturaMotor("tesseract", "original", "AP4", "AP4", False, 0.5),
        ),
    )


@pytest.fixture(params=["memoria", "sqlite"])
def repositorio(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[RepositorioResultados]:
    if request.param == "memoria":
        yield RepositorioEnMemoria()
        return
    motor = crear_motor_bd(f"sqlite:///{tmp_path / 'vigia.db'}")
    crear_esquema(motor)
    yield RepositorioSQL(motor)
    motor.dispose()


def test_obtener_inexistente(repositorio: RepositorioResultados) -> None:
    assert repositorio.obtener(RADICADO, FECHA_CORTE) is None


def test_ida_y_vuelta_conserva_todo(repositorio: RepositorioResultados) -> None:
    original = resultado()
    assert repositorio.guardar(original) is True
    leido = repositorio.obtener(RADICADO, FECHA_CORTE)
    assert leido == original
    assert leido is not None
    assert leido.lecturas == original.lecturas


def test_segundo_guardado_no_sobrescribe(repositorio: RepositorioResultados) -> None:
    repositorio.guardar(resultado())
    otro = resultado(codigo_ejemplo("10974", EstadoObligacion.EMBARGO))
    assert repositorio.guardar(otro) is False
    leido = repositorio.obtener(RADICADO, FECHA_CORTE)
    assert leido is not None
    assert leido.codigo == codigo_ejemplo()


def test_la_clave_es_radicado_y_fecha(repositorio: RepositorioResultados) -> None:
    assert repositorio.guardar(resultado()) is True
    assert repositorio.guardar(resultado(fecha=date(2026, 11, 13))) is True
    assert repositorio.guardar(resultado(radicado=Radicado("PCA-2026-00023"))) is True


def test_memoria_lista_todos() -> None:
    repo = RepositorioEnMemoria()
    repo.guardar(resultado())
    assert [r.radicado for r in repo.todos()] == [RADICADO]


def test_sqlite_tiene_claves_foraneas_activas(tmp_path: Path) -> None:
    motor = crear_motor_bd(f"sqlite:///{tmp_path / 'fk.db'}")
    with motor.connect() as conexion:
        assert conexion.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_el_modelo_compila_para_sql_server() -> None:
    """Sin servidor: garantiza que el ORM genera DDL válido para el dialecto mssql."""
    ddl = str(CreateTable(FilaResultado.__table__).compile(dialect=mssql.dialect()))  # type: ignore[arg-type]
    assert "CONSTRAINT uq_vigia_resultados_radicado_corte UNIQUE (radicado, fecha_corte)" in ddl
    assert "IDENTITY" in ddl
    assert set(Base.metadata.tables) == {"vigia_resultados", "vigia_lecturas"}


def test_script_ddl_de_sql_server_coincide_con_el_modelo() -> None:
    """El DDL que revisa el DBA y el modelo del ORM no deben divergir."""
    script = (Path(__file__).parents[2] / "sql" / "001_esquema.sql").read_text(encoding="utf-8")
    for tabla in Base.metadata.sorted_tables:
        assert f"dbo.{tabla.name}" in script
        for columna in tabla.columns:
            assert columna.name in script, f"{tabla.name}.{columna.name} falta en el DDL"
    assert "uq_vigia_resultados_radicado_corte" in script
