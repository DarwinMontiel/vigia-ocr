"""Repositorio SQLAlchemy. El mismo código corre contra SQL Server (pyodbc) y SQLite.

La idempotencia la garantiza la base de datos con la restricción única
``(radicado, fecha_corte)``, no el código: si dos bots guardan el mismo radicado a la vez,
uno gana y el otro recibe ``IntegrityError``, que aquí se traduce en ``False``.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    event,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    selectinload,
    sessionmaker,
)

from vigia_ocr.dominio.codigo import EstadoObligacion
from vigia_ocr.dominio.modelos import (
    LecturaMotor,
    MetodoVeredicto,
    Radicado,
    ResultadoConsulta,
)


class Base(DeclarativeBase):
    pass


class FilaResultado(Base):
    __tablename__ = "vigia_resultados"
    __table_args__ = (
        UniqueConstraint("radicado", "fecha_corte", name="uq_vigia_resultados_radicado_corte"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    radicado: Mapped[str] = mapped_column(String(20))
    fecha_corte: Mapped[date] = mapped_column(Date)
    codigo: Mapped[str] = mapped_column(String(8))
    estado: Mapped[str] = mapped_column(String(2))
    confianza: Mapped[float] = mapped_column(Float)
    metodo: Mapped[str] = mapped_column(String(20))
    imagenes_consultadas: Mapped[int] = mapped_column(Integer)
    consultado_en: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    lecturas: Mapped[list[FilaLectura]] = relationship(
        back_populates="resultado", cascade="all, delete-orphan", order_by="FilaLectura.id"
    )


class FilaLectura(Base):
    """Auditoría: qué leyó cada motor. Permite explicar cualquier resultado a posteriori."""

    __tablename__ = "vigia_lecturas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resultado_id: Mapped[int] = mapped_column(ForeignKey("vigia_resultados.id"))
    motor: Mapped[str] = mapped_column(String(20))
    variante: Mapped[str] = mapped_column(String(30))
    texto_crudo: Mapped[str] = mapped_column(String(64))
    texto_normalizado: Mapped[str] = mapped_column(String(64))
    valido: Mapped[bool] = mapped_column(Boolean)
    peso: Mapped[float] = mapped_column(Float)
    resultado: Mapped[FilaResultado] = relationship(back_populates="lecturas")


def crear_motor_bd(url: str, *, echo: bool = False) -> Engine:
    """Crea el engine. En SQLite activa claves foráneas (vienen apagadas por defecto)."""
    motor = create_engine(url, echo=echo, pool_pre_ping=True)
    if motor.dialect.name == "sqlite":

        @event.listens_for(motor, "connect")
        def _activar_fk(conexion: object, _registro: object) -> None:
            cursor = conexion.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return motor


def crear_esquema(motor: Engine) -> None:
    """Para SQLite y pruebas. En SQL Server se usa ``sql/001_esquema.sql``, revisable por un DBA."""
    Base.metadata.create_all(motor)


class RepositorioSQL:
    def __init__(self, motor: Engine) -> None:
        self._sesiones = sessionmaker(motor, expire_on_commit=False)

    def obtener(self, radicado: Radicado, fecha_corte: date) -> ResultadoConsulta | None:
        # Sesión nueva en cada lectura: la verificación tras guardar debe leer lo que de
        # verdad quedó en la base de datos, no un objeto en la caché de la sesión.
        with self._sesiones() as sesion:
            fila = sesion.scalar(
                select(FilaResultado)
                .options(selectinload(FilaResultado.lecturas))
                .where(
                    FilaResultado.radicado == radicado.valor,
                    FilaResultado.fecha_corte == fecha_corte,
                )
            )
            return _a_dominio(fila) if fila is not None else None

    def guardar(self, resultado: ResultadoConsulta) -> bool:
        fila = FilaResultado(
            radicado=resultado.radicado.valor,
            fecha_corte=resultado.fecha_corte,
            codigo=resultado.codigo,
            estado=resultado.estado.value,
            confianza=resultado.confianza,
            metodo=resultado.metodo.value,
            imagenes_consultadas=resultado.imagenes_consultadas,
            consultado_en=resultado.consultado_en.replace(tzinfo=None),
            lecturas=[
                FilaLectura(
                    motor=x.motor,
                    variante=x.variante,
                    texto_crudo=x.texto_crudo[:64],
                    texto_normalizado=x.texto_normalizado[:64],
                    valido=x.valido,
                    peso=x.peso,
                )
                for x in resultado.lecturas
            ],
        )
        with self._sesiones() as sesion:
            sesion.add(fila)
            try:
                sesion.commit()
            except IntegrityError:
                sesion.rollback()
                return False
        return True


def _a_dominio(fila: FilaResultado) -> ResultadoConsulta:
    return ResultadoConsulta(
        radicado=Radicado(fila.radicado),
        fecha_corte=fila.fecha_corte,
        codigo=fila.codigo,
        estado=EstadoObligacion(fila.estado),
        confianza=fila.confianza,
        metodo=MetodoVeredicto(fila.metodo),
        imagenes_consultadas=fila.imagenes_consultadas,
        consultado_en=fila.consultado_en,
        lecturas=tuple(
            LecturaMotor(
                motor=x.motor,
                variante=x.variante,
                texto_crudo=x.texto_crudo,
                texto_normalizado=x.texto_normalizado,
                valido=x.valido,
                peso=x.peso,
            )
            for x in fila.lecturas
        ),
    )
