"""Regenera las imágenes de ``docs/imagenes`` (README y demo).

    python scripts/generar_imagenes_docs.py

Requiere Chrome y ``.[ocr]``. Levanta el portal ficticio en un puerto libre, toma capturas
con Selenium (el mismo navegador que usa el bot) y arma la lámina de preprocesado.
"""

from __future__ import annotations

import socket
import tempfile
import threading
import time
from pathlib import Path

import httpx
import uvicorn
from PIL import Image, ImageDraw, ImageFont
from selenium.webdriver.common.by import By

from vigia_ocr.adaptadores.portal.selenium_portal import crear_chrome
from vigia_ocr.adaptadores.preprocesado import VARIANTES_POR_DEFECTO
from vigia_ocr.config import Configuracion
from vigia_ocr.demo_web.construir import construir_demo
from vigia_ocr.portal_ficticio import catalogo
from vigia_ocr.portal_ficticio.app import crear_app
from vigia_ocr.sintetico.generador import generar_lote

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "docs" / "imagenes"


def lamina_preprocesado(destino: Path, cantidad: int = 4, semilla: int = 2026) -> None:
    """Una fila por muestra: imagen del portal y sus cinco variantes."""
    fuente = ImageFont.load_default(size=15)
    columnas = ["portal", *(v.nombre for v in VARIANTES_POR_DEFECTO)]
    ancho_celda, alto_celda, margen = 240, 72, 12
    ancho = len(columnas) * (ancho_celda + margen) + margen
    alto = 30 + cantidad * (alto_celda + margen) + margen
    lamina = Image.new("RGB", (ancho, alto), (247, 245, 240))
    dibujo = ImageDraw.Draw(lamina)
    for c, nombre in enumerate(columnas):
        dibujo.text(
            (margen + c * (ancho_celda + margen), 8), nombre, font=fuente, fill=(40, 40, 40)
        )
    for f, muestra in enumerate(generar_lote(cantidad, semilla)):
        imagenes = [muestra.imagen, *(v.aplicar(muestra.imagen) for v in VARIANTES_POR_DEFECTO)]
        for c, imagen in enumerate(imagenes):
            celda = imagen.convert("RGB").resize((ancho_celda, alto_celda))
            lamina.paste(
                celda, (margen + c * (ancho_celda + margen), 30 + f * (alto_celda + margen))
            )
    lamina.save(destino, optimize=True)


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def capturas(destino: Path) -> None:
    puerto = puerto_libre()
    servidor = uvicorn.Server(
        uvicorn.Config(crear_app(semilla=2026), host="127.0.0.1", port=puerto, log_level="warning")
    )
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    url = f"http://127.0.0.1:{puerto}"
    for _ in range(50):
        try:
            httpx.get(f"{url}/salud")
            break
        except httpx.HTTPError:
            time.sleep(0.1)

    driver = crear_chrome(headless=True)
    try:
        driver.set_window_size(1100, 760)
        driver.get(f"{url}/consulta?radicado={catalogo.EXPEDIENTES[0].radicado}")
        time.sleep(0.5)
        driver.save_screenshot(str(destino / "portal-ficha.png"))

        with tempfile.TemporaryDirectory() as temporal:
            sitio = Path(temporal) / "site"
            config = Configuracion(motores=["ddddocr", "tesseract"], _env_file=None)  # type: ignore[call-arg]
            indice = construir_demo(
                sitio, config, cantidad=12, evaluacion_json=RAIZ / "docs" / "evaluacion.json"
            )
            driver.set_window_size(1200, 1500)
            driver.get(indice.as_uri())
            time.sleep(0.5)
            driver.find_elements(By.CSS_SELECTOR, ".miniatura")[1].click()
            time.sleep(0.3)
            driver.save_screenshot(str(destino / "demo-web.png"))
    finally:
        driver.quit()
        servidor.should_exit = True


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    lamina_preprocesado(DESTINO / "preprocesado.png")
    capturas(DESTINO)
    print(f"Imágenes en {DESTINO}")


if __name__ == "__main__":
    main()
