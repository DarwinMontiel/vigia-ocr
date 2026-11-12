"""Construye la demo estática con lecturas reales de la cadena OCR.

No hay OCR en el navegador: el sitio muestra lo que la cadena *realmente* leyó al construirlo
(cada variante preprocesada, la lectura de cada motor y el veredicto de la votación).
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from vigia_ocr.adaptadores.ocr import crear_motores
from vigia_ocr.adaptadores.preprocesado import variantes_por_nombre
from vigia_ocr.aplicacion.lector import LectorConsenso
from vigia_ocr.config import Configuracion
from vigia_ocr.dominio.codigo import EstadoObligacion
from vigia_ocr.portal_ficticio import catalogo
from vigia_ocr.sintetico.generador import generar_lote

MARCADOR = "/*__DATOS__*/null"


def construir_demo(
    salida: Path,
    config: Configuracion,
    *,
    cantidad: int = 12,
    semilla: int = 2026,
    evaluacion_json: Path | None = None,
) -> Path:
    imagenes = salida / "img"
    imagenes.mkdir(parents=True, exist_ok=True)
    motores = crear_motores(config.motores, omitir_no_disponibles=True)
    variantes = variantes_por_nombre(config.variantes)
    lector = LectorConsenso.desde_motores(
        motores, variantes, min_acuerdo=config.min_acuerdo, parada_temprana=False
    )

    casos = []
    for indice, muestra in enumerate(generar_lote(cantidad, semilla)):
        expediente = catalogo.EXPEDIENTES[indice % len(catalogo.EXPEDIENTES)]
        base = f"caso{indice:02d}"
        muestra.imagen.save(imagenes / f"{base}.png")
        etapas = []
        for variante in variantes:
            archivo = f"{base}_{variante.nombre}.png"
            variante.aplicar(muestra.imagen).save(imagenes / archivo)
            etapas.append({"variante": variante.nombre, "imagen": f"img/{archivo}"})
        veredicto = lector.leer(muestra.imagen)
        casos.append(
            {
                "imagen": f"img/{base}.png",
                "verdadero": muestra.codigo,
                "radicado": expediente.radicado,
                "demandado": expediente.demandado,
                "nota": expediente.nota,
                "etapas": etapas,
                "lecturas": [
                    {
                        "motor": x.motor,
                        "variante": x.variante,
                        "crudo": x.texto_crudo,
                        "normalizado": x.texto_normalizado,
                        "valido": x.valido,
                    }
                    for x in veredicto.lecturas
                ],
                "codigo": veredicto.codigo,
                "metodo": veredicto.metodo.value,
                "confianza": veredicto.confianza,
                "estado": veredicto.estado.descripcion if veredicto.estado else None,
            }
        )

    evaluacion = (
        json.loads(evaluacion_json.read_text(encoding="utf-8"))
        if evaluacion_json is not None and evaluacion_json.exists()
        else None
    )
    datos = {
        "casos": casos,
        "motores": [m.nombre for m in motores],
        "estados": {e.value: e.descripcion for e in EstadoObligacion},
        "evaluacion": evaluacion,
    }
    plantilla = resources.files("vigia_ocr.demo_web").joinpath("plantilla.html").read_text("utf-8")
    if MARCADOR not in plantilla:
        raise RuntimeError("La plantilla de la demo no tiene el marcador de datos")
    html = plantilla.replace(MARCADOR, json.dumps(datos, ensure_ascii=False).replace("</", "<\\/"))
    destino = salida / "index.html"
    destino.write_text(html, encoding="utf-8")
    return destino
