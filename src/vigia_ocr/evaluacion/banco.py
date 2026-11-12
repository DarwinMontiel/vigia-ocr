"""Banco de evaluación: mide cuánto aporta cada capa de la cadena OCR.

Sobre un lote sintético reproducible (misma semilla = mismas imágenes) se evalúan, de la más
simple a la de producción:

1. Cada motor solo sobre la imagen cruda, aceptando lo que lea (así se empezó).
2. Cada motor sobre la mejor variante preprocesada + normalización posicional.
3. Cada motor sobre todas las variantes, con votación y validación por dígito de verificación.
4. Todos los motores y variantes con votación y validación (una sola imagen).
5. Producción: lo anterior + pedir imagen nueva al portal si no hay consenso.
6. Ablación: producción quitando un motor a la vez (cuánto aporta cada uno).

Cada configuración se reporta con tres números que suman 100 %: **acierto**, **error
silencioso** (entregó un código equivocado: lo peor que puede pasar) y **sin respuesta** (el
bot reconoce que no sabe y el radicado queda pendiente).

La ejecución usa el código de producción (``LectorConsenso``, ``votar``, ``normalizar``), no
una reimplementación: lo medido es lo que corre.
"""

from __future__ import annotations

import hashlib
import json
import platform
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from functools import partial
from importlib import metadata
from pathlib import Path

import structlog
from PIL import Image

from vigia_ocr.adaptadores.preprocesado import ORIGINAL, Variante
from vigia_ocr.aplicacion.lector import LectorConsenso
from vigia_ocr.dominio.normalizacion import limpiar, normalizar
from vigia_ocr.puertos import MotorOCR
from vigia_ocr.sintetico.generador import Muestra, ParametrosRuido, generar_lote, renderizar

log = structlog.get_logger(__name__)

Respuesta = str | None


class MotorMedido:
    """Envuelve un motor: memoriza lecturas (cada imagen se lee una vez) y mide su tiempo."""

    def __init__(self, motor: MotorOCR) -> None:
        self._motor = motor
        self._cache: dict[tuple[str, str], str] = {}
        self.lecturas_reales = 0
        self.segundos = 0.0

    @property
    def nombre(self) -> str:
        return self._motor.nombre

    def leer(self, imagen: Image.Image) -> str:
        clave = (hashlib.blake2b(imagen.tobytes(), digest_size=16).hexdigest(), imagen.mode)
        if clave not in self._cache:
            inicio = time.perf_counter()
            self._cache[clave] = self._motor.leer(imagen)
            self.segundos += time.perf_counter() - inicio
            self.lecturas_reales += 1
        return self._cache[clave]

    @property
    def ms_por_lectura(self) -> float:
        return 1000 * self.segundos / self.lecturas_reales if self.lecturas_reales else 0.0


@dataclass(frozen=True, slots=True)
class FilaInforme:
    configuracion: str
    grupo: str
    total: int
    aciertos: int
    errores: int
    sin_respuesta: int
    imagenes_promedio: float = 1.0
    lecturas_promedio: float = 1.0

    @property
    def acierto(self) -> float:
        return self.aciertos / self.total if self.total else 0.0

    @property
    def error_silencioso(self) -> float:
        return self.errores / self.total if self.total else 0.0

    @property
    def tasa_sin_respuesta(self) -> float:
        return self.sin_respuesta / self.total if self.total else 0.0


@dataclass(slots=True)
class Informe:
    cantidad: int
    semilla: int
    max_imagenes: int
    motores: list[str]
    motores_omitidos: list[str]
    variantes: list[str]
    filas: list[FilaInforme] = field(default_factory=list)
    ms_por_lectura: dict[str, float] = field(default_factory=dict)
    generado_en: str = field(
        default_factory=lambda: datetime.now().astimezone().isoformat("T", "seconds")
    )
    entorno: dict[str, str] = field(default_factory=dict)

    def a_json(self) -> str:
        datos = asdict(self)
        for fila, original in zip(datos["filas"], self.filas, strict=True):
            fila["acierto"] = round(original.acierto, 4)
            fila["error_silencioso"] = round(original.error_silencioso, 4)
            fila["sin_respuesta_pct"] = round(original.tasa_sin_respuesta, 4)
        return json.dumps(datos, ensure_ascii=False, indent=2)


def _lectura_cruda(motor: MotorOCR, imagen: Image.Image) -> str:
    """Así se empezó: aceptar lo que el motor lea sobre la imagen sin tocar."""
    return limpiar(motor.leer(ORIGINAL.aplicar(imagen))).upper()


def _lectura_preprocesada(motor: MotorOCR, variante: Variante, imagen: Image.Image) -> str:
    return normalizar(motor.leer(variante.aplicar(imagen)))


def _semilla_reintento(muestra: Muestra, intento: int) -> int:
    """Semilla de la imagen ``intento`` de una muestra (el portal genera ruido nuevo)."""
    return (muestra.semilla * 1_000_003 + intento) % (2**48)


class BancoEvaluacion:
    def __init__(
        self,
        motores: Sequence[MotorOCR],
        variantes: Sequence[Variante],
        *,
        cantidad: int = 300,
        semilla: int = 2026,
        max_imagenes: int = 3,
        min_acuerdo: int = 2,
        parametros: ParametrosRuido | None = None,
        motores_omitidos: Sequence[str] = (),
    ) -> None:
        if not motores:
            raise ValueError("Se necesita al menos un motor para evaluar")
        self._motores = [MotorMedido(m) for m in motores]
        self._variantes = tuple(variantes)
        self._cantidad = cantidad
        self._semilla = semilla
        self._max_imagenes = max_imagenes
        self._min_acuerdo = min_acuerdo
        self._parametros = parametros
        self._omitidos = list(motores_omitidos)

    def ejecutar(self, progreso: Callable[[str], None] | None = None) -> Informe:
        muestras = generar_lote(self._cantidad, self._semilla, self._parametros)
        informe = Informe(
            cantidad=self._cantidad,
            semilla=self._semilla,
            max_imagenes=self._max_imagenes,
            motores=[m.nombre for m in self._motores],
            motores_omitidos=self._omitidos,
            variantes=[v.nombre for v in self._variantes],
            entorno=_entorno(),
        )
        aviso = progreso or (lambda _texto: None)
        mejor = self._variantes[0]

        for motor in self._motores:
            aviso(f"{motor.nombre}: imagen cruda")
            informe.filas.append(
                self._evaluar_directo(
                    f"{motor.nombre} · imagen cruda, sin validar",
                    "1. Motor solo",
                    muestras,
                    partial(_lectura_cruda, motor),
                )
            )
        for motor in self._motores:
            aviso(f"{motor.nombre}: preprocesado")
            informe.filas.append(
                self._evaluar_directo(
                    f"{motor.nombre} · {mejor.nombre} + normalización",
                    "2. Preprocesado",
                    muestras,
                    partial(_lectura_preprocesada, motor, mejor),
                )
            )
        for motor in self._motores:
            aviso(f"{motor.nombre}: votación entre variantes")
            lector = LectorConsenso.desde_motores(
                [motor], self._variantes, min_acuerdo=self._min_acuerdo, parada_temprana=False
            )
            informe.filas.append(
                self._evaluar_lector(
                    f"{motor.nombre} · {len(self._variantes)} variantes + votación + DV",
                    "3. Votación por motor",
                    muestras,
                    lector,
                    max_imagenes=1,
                )
            )
        if len(self._motores) > 1:
            aviso("todos los motores: votación")
            lector_todos = LectorConsenso.desde_motores(
                self._motores,
                self._variantes,
                min_acuerdo=self._min_acuerdo,
                parada_temprana=False,
            )
            informe.filas.append(
                self._evaluar_lector(
                    f"{' + '.join(m.nombre for m in self._motores)} · votación + DV",
                    "4. Votación entre motores",
                    muestras,
                    lector_todos,
                    max_imagenes=1,
                )
            )
        aviso("cadena de producción")
        lector_produccion = LectorConsenso.desde_motores(
            self._motores, self._variantes, min_acuerdo=self._min_acuerdo, parada_temprana=True
        )
        informe.filas.append(
            self._evaluar_lector(
                f"Producción · votación + DV + hasta {self._max_imagenes} imágenes",
                "5. Producción",
                muestras,
                lector_produccion,
                max_imagenes=self._max_imagenes,
            )
        )
        if len(self._motores) > 1:
            # Ablación: cuánto aporta cada motor a la cadena de producción.
            for excluido in self._motores:
                aviso(f"producción sin {excluido.nombre}")
                restantes = [m for m in self._motores if m is not excluido]
                informe.filas.append(
                    self._evaluar_lector(
                        f"Producción sin {excluido.nombre}",
                        "6. Ablación",
                        muestras,
                        LectorConsenso.desde_motores(
                            restantes,
                            self._variantes,
                            min_acuerdo=self._min_acuerdo,
                            parada_temprana=True,
                        ),
                        max_imagenes=self._max_imagenes,
                    )
                )
        informe.ms_por_lectura = {m.nombre: round(m.ms_por_lectura, 1) for m in self._motores}
        return informe

    @staticmethod
    def _evaluar_directo(
        nombre: str,
        grupo: str,
        muestras: Sequence[Muestra],
        leer: Callable[[Image.Image], str],
    ) -> FilaInforme:
        aciertos = errores = sin_respuesta = 0
        for muestra in muestras:
            texto = leer(muestra.imagen)
            if not texto:
                sin_respuesta += 1
            elif texto == muestra.codigo:
                aciertos += 1
            else:
                errores += 1
        return FilaInforme(nombre, grupo, len(muestras), aciertos, errores, sin_respuesta)

    def _evaluar_lector(
        self,
        nombre: str,
        grupo: str,
        muestras: Sequence[Muestra],
        lector: LectorConsenso,
        *,
        max_imagenes: int,
    ) -> FilaInforme:
        aciertos = errores = sin_respuesta = 0
        imagenes = lecturas = 0
        for muestra in muestras:
            respuesta: Respuesta = None
            for intento in range(max_imagenes):
                imagen = (
                    muestra.imagen
                    if intento == 0
                    else renderizar(
                        muestra.codigo, _semilla_reintento(muestra, intento), self._parametros
                    )
                )
                veredicto = lector.leer(imagen)
                imagenes += 1
                lecturas += len(veredicto.lecturas)
                if veredicto.aceptado:
                    respuesta = veredicto.codigo
                    break
            if respuesta is None:
                sin_respuesta += 1
            elif respuesta == muestra.codigo:
                aciertos += 1
            else:
                errores += 1
        total = len(muestras)
        return FilaInforme(
            nombre,
            grupo,
            total,
            aciertos,
            errores,
            sin_respuesta,
            imagenes_promedio=round(imagenes / total, 2),
            lecturas_promedio=round(lecturas / total, 2),
        )


def _version(paquete: str) -> str:
    try:
        return metadata.version(paquete)
    except metadata.PackageNotFoundError:
        return "no instalado"


def _entorno() -> dict[str, str]:
    entorno = {
        "python": platform.python_version(),
        "sistema": f"{platform.system()} {platform.machine()}",
        "pillow": _version("pillow"),
        "opencv": _version("opencv-python-headless"),
        "ddddocr": _version("ddddocr"),
        "pytesseract": _version("pytesseract"),
        "easyocr": _version("easyocr"),
    }
    try:
        import pytesseract

        entorno["tesseract"] = str(pytesseract.get_tesseract_version())
    except Exception:
        entorno["tesseract"] = "no instalado"
    return entorno


def _pct(valor: float) -> str:
    return f"{100 * valor:.1f} %".replace(".", ",")


def _num(valor: float, decimales: int = 2) -> str:
    return f"{valor:.{decimales}f}".replace(".", ",")


def informe_a_markdown(informe: Informe) -> str:
    lineas = [
        "# Evaluación de la cadena OCR",
        "",
        "> Archivo generado por `vigia evaluar` (no editar a mano). "
        "Los números son los que midió esta ejecución.",
        "",
        f"- **Muestras:** {informe.cantidad} imágenes sintéticas, semilla `{informe.semilla}` "
        "(reproducible).",
        f"- **Motores evaluados:** {', '.join(informe.motores)}"
        + (
            f" · **omitidos (no instalados):** {', '.join(informe.motores_omitidos)}"
            if informe.motores_omitidos
            else ""
        ),
        f"- **Variantes de preprocesado:** {', '.join(f'`{v}`' for v in informe.variantes)}",
        f"- **Generado:** {informe.generado_en}",
        "",
        "| Capa | Configuración | Acierto | Error silencioso | Sin respuesta "
        "| Imágenes/caso | Lecturas/caso |",
        "|---|---|--:|--:|--:|--:|--:|",
    ]
    for f in informe.filas:
        lineas.append(
            f"| {f.grupo} | {f.configuracion} | **{_pct(f.acierto)}** | "
            f"{_pct(f.error_silencioso)} | {_pct(f.tasa_sin_respuesta)} | "
            f"{_num(f.imagenes_promedio)} | {_num(f.lecturas_promedio)} |"
        )
    lineas += [
        "",
        "**Cómo leer la tabla.** *Acierto*: el código entregado es el correcto. *Error "
        "silencioso*: se entregó un código equivocado (es el peor caso: termina en la base de "
        "datos). *Sin respuesta*: la cadena reconoce que no hay consenso y el radicado queda "
        "pendiente para la siguiente corrida. Las tres columnas suman 100 %.",
        "",
        "## Costo por lectura",
        "",
        "| Motor | ms promedio por lectura |",
        "|---|--:|",
        *[f"| {m} | {_num(ms, 1)} |" for m, ms in informe.ms_por_lectura.items()],
        "",
        "## Entorno",
        "",
        "| Componente | Versión |",
        "|---|---|",
        *[f"| {k} | {v} |" for k, v in informe.entorno.items()],
        "",
    ]
    return "\n".join(lineas)


def escribir_informe(informe: Informe, destino_md: Path) -> Path:
    destino_md.parent.mkdir(parents=True, exist_ok=True)
    destino_md.write_text(informe_a_markdown(informe), encoding="utf-8")
    destino_json = destino_md.with_suffix(".json")
    destino_json.write_text(informe.a_json() + "\n", encoding="utf-8")
    return destino_json
