"""Interfaz de línea de comandos: ``vigia --help``."""

from __future__ import annotations

import csv
import io
import sys
from datetime import date
from pathlib import Path
from typing import Annotated

import structlog
import typer
from PIL import Image

from vigia_ocr import __version__
from vigia_ocr.config import Configuracion, obtener_configuracion
from vigia_ocr.dominio.modelos import Radicado
from vigia_ocr.registro import configurar_registro

app = typer.Typer(
    name="vigia",
    help="Vigía OCR: consulta el estado de radicados en un portal que lo publica como imagen.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode=None,
)
log = structlog.get_logger("vigia.cli")

CODIGO_PENDIENTES = 2


def _config() -> Configuracion:
    config = obtener_configuracion()
    configurar_registro(config.log_formato, config.log_nivel)
    return config


def leer_radicados(archivo: Path) -> list[Radicado]:
    """Lee la columna ``radicado`` de un CSV. Filas inválidas se reportan y se omiten."""
    radicados: list[Radicado] = []
    with archivo.open(encoding="utf-8-sig", newline="") as manejador:
        for numero, fila in enumerate(csv.DictReader(manejador), start=2):
            valor = (fila.get("radicado") or "").strip()
            try:
                radicados.append(Radicado(valor))
            except ValueError as error:
                log.warning("Fila omitida", archivo=str(archivo), fila=numero, motivo=str(error))
    return list(dict.fromkeys(radicados))  # sin duplicados, conservando el orden


@app.callback(invoke_without_command=True)
def _principal(
    version: Annotated[bool, typer.Option("--version", help="Muestra la versión.")] = False,
) -> None:
    for flujo in (sys.stdout, sys.stderr):  # consolas de Windows en cp1252
        if isinstance(flujo, io.TextIOWrapper):
            flujo.reconfigure(encoding="utf-8")
    if version:
        typer.echo(f"vigia-ocr {__version__}")
        raise typer.Exit


@app.command()
def portal(
    host: str = "127.0.0.1",
    puerto: int = 8000,
    tasa_fallos: Annotated[
        float, typer.Option(min=0.0, max=1.0, help="Probabilidad de responder 503.")
    ] = 0.0,
    semilla: Annotated[int | None, typer.Option(help="Semilla del ruido (reproducible).")] = None,
) -> None:
    """Levanta el portal ficticio de Puerto Candela."""
    import uvicorn

    from vigia_ocr.portal_ficticio.app import crear_app

    _config()
    log.info("Portal ficticio en marcha", url=f"http://{host}:{puerto}", tasa_fallos=tasa_fallos)
    uvicorn.run(crear_app(semilla=semilla, tasa_fallos=tasa_fallos), host=host, port=puerto)


@app.command()
def consultar(
    archivo: Annotated[Path, typer.Argument(exists=True, dir_okay=False)] = Path(
        "datos/radicados_demo.csv"
    ),
    fecha_corte: Annotated[str | None, typer.Option(help="AAAA-MM-DD. Por defecto, hoy.")] = None,
    portal_url: Annotated[str | None, typer.Option(help="Sobrescribe VIGIA_PORTAL_URL.")] = None,
) -> None:
    """Consulta un lote de radicados con Selenium y guarda los estados en la base de datos."""
    from vigia_ocr.adaptadores.portal.selenium_portal import PortalSelenium
    from vigia_ocr.contenedor import (
        Dependencias,
        RelojSistema,
        crear_lector,
        crear_repositorio_sql,
        crear_servicio,
    )

    config = _config()
    corte = date.fromisoformat(fecha_corte) if fecha_corte else date.today()
    radicados = leer_radicados(archivo)
    repositorio = crear_repositorio_sql(config)
    lector = crear_lector(config)
    log.info("Inicio del lote", radicados=len(radicados), fecha_corte=corte.isoformat())

    with PortalSelenium(
        portal_url or config.portal_url,
        headless=config.navegador_headless,
        espera_s=config.navegador_espera_s,
        binario=config.navegador_binario,
        chromedriver=config.chromedriver,
    ) as navegador:
        servicio = crear_servicio(
            config, Dependencias(navegador, repositorio, lector, RelojSistema())
        )
        resumen = servicio.procesar_lote(radicados, corte)

    for resultado in resumen.resultados:
        guardado = resultado.resultado
        detalle = (
            f"{guardado.codigo}  {guardado.estado.descripcion}" if guardado else resultado.detalle
        )
        typer.echo(f"{resultado.radicado.valor:16} {resultado.desenlace.value:22} {detalle}")
    typer.echo(f"\n{resumen.exitosos}/{resumen.total} radicados con estado confirmado.")
    if resumen.pendientes:
        raise typer.Exit(CODIGO_PENDIENTES)


@app.command()
def leer(
    imagenes: Annotated[list[Path], typer.Argument(exists=True, dir_okay=False)],
) -> None:
    """Lee una o varias imágenes con la cadena OCR y muestra el detalle de la votación."""
    from vigia_ocr.contenedor import crear_lector

    lector = crear_lector(_config())
    for ruta in imagenes:
        with Image.open(ruta) as imagen:
            veredicto = lector.leer(imagen.convert("RGB"))
        typer.echo(
            f"\n{ruta.name}: {veredicto.codigo or 'SIN CONSENSO'}  "
            f"({veredicto.metodo.value}, confianza {veredicto.confianza:.2f})"
        )
        if veredicto.estado:
            typer.echo(f"  Estado: {veredicto.estado.descripcion}")
        for x in veredicto.lecturas:
            marca = "ok" if x.valido else "--"
            typer.echo(
                f"  [{marca}] {x.motor:10} {x.variante:18} {x.texto_crudo!r:14} "
                f"-> {x.texto_normalizado}"
            )


@app.command()
def muestras(
    cantidad: Annotated[int, typer.Option(min=1, max=5000)] = 12,
    semilla: int = 2026,
    salida: Path = Path("muestras"),
) -> None:
    """Genera imágenes sintéticas con su código verdadero en el nombre del archivo."""
    from vigia_ocr.sintetico.generador import generar_lote

    salida.mkdir(parents=True, exist_ok=True)
    for indice, muestra in enumerate(generar_lote(cantidad, semilla), start=1):
        muestra.imagen.save(salida / f"{indice:04d}_{muestra.codigo}.png")
    typer.echo(f"{cantidad} imágenes en {salida}/")


@app.command()
def evaluar(
    cantidad: Annotated[int, typer.Option(min=10, max=10000)] = 300,
    semilla: int = 2026,
    motores: Annotated[
        str, typer.Option(help="Separados por coma, del más rápido al más lento.")
    ] = "ddddocr,tesseract,easyocr",
    max_imagenes: Annotated[int, typer.Option(min=1, max=10)] = 3,
    salida: Path = Path("docs/evaluacion.md"),
) -> None:
    """Mide el acierto de cada motor, del preprocesado y de la votación. Escribe docs/."""
    from vigia_ocr.adaptadores.ocr import FABRICAS
    from vigia_ocr.adaptadores.preprocesado import VARIANTES_POR_DEFECTO
    from vigia_ocr.dominio.errores import MotorNoDisponible
    from vigia_ocr.evaluacion.banco import BancoEvaluacion, escribir_informe, informe_a_markdown

    _config()
    instancias = []
    omitidos = []
    for nombre in [m.strip() for m in motores.split(",") if m.strip()]:
        if nombre not in FABRICAS:
            raise typer.BadParameter(f"Motor desconocido: {nombre}")
        try:
            instancias.append(FABRICAS[nombre]())
        except MotorNoDisponible as error:
            log.warning("Motor omitido en la evaluación", motor=nombre, motivo=str(error))
            omitidos.append(nombre)
    if not instancias:
        typer.echo("Ningún motor disponible. Instala al menos: pip install -e '.[ocr]'", err=True)
        raise typer.Exit(1)

    banco = BancoEvaluacion(
        instancias,
        VARIANTES_POR_DEFECTO,
        cantidad=cantidad,
        semilla=semilla,
        max_imagenes=max_imagenes,
        motores_omitidos=omitidos,
    )
    informe = banco.ejecutar(progreso=lambda texto: log.info("Evaluando", paso=texto))
    escribir_informe(informe, salida)
    typer.echo(informe_a_markdown(informe))
    typer.echo(f"Informe escrito en {salida} y {salida.with_suffix('.json')}")


@app.command("db-crear")
def db_crear() -> None:
    """Crea las tablas con SQLAlchemy (SQLite). Para SQL Server usa sql/001_esquema.sql."""
    from vigia_ocr.adaptadores.persistencia.sql import crear_esquema, crear_motor_bd

    config = _config()
    crear_esquema(crear_motor_bd(config.base_datos_url))
    typer.echo(f"Esquema creado en {config.base_datos_url.split('@')[-1]}")


@app.command("demo-web")
def demo_web(
    salida: Path = Path("site"),
    cantidad: Annotated[int, typer.Option(min=1, max=60)] = 12,
    semilla: int = 2026,
    motores: str = "ddddocr,tesseract",
    evaluacion: Annotated[
        Path, typer.Option(help="JSON del banco de evaluación a mostrar.")
    ] = Path("docs/evaluacion.json"),
) -> None:
    """Construye la demo estática (GitHub Pages) con lecturas reales de la cadena OCR."""
    from vigia_ocr.demo_web.construir import construir_demo

    config = _config()
    config_demo = config.model_copy(update={"motores": motores.split(",")})
    destino = construir_demo(
        salida, config_demo, cantidad=cantidad, semilla=semilla, evaluacion_json=evaluacion
    )
    typer.echo(f"Demo construida en {destino}")


def main() -> None:  # pragma: no cover - punto de entrada de `python -m vigia_ocr`
    app(prog_name="vigia")
    sys.exit(0)
