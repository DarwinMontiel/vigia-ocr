"""Navegación del portal con Selenium (Chrome).

Flujo por radicado: abrir el formulario, escribir el radicado, consultar, esperar la ficha o
el mensaje de error, esperar a que la imagen termine de cargar, capturar la pantalla y
recortar la imagen.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Self

import structlog
from PIL import Image
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from vigia_ocr.adaptadores.portal.recorte import Caja, recortar
from vigia_ocr.dominio.errores import PortalNoDisponible, RadicadoInexistente
from vigia_ocr.dominio.modelos import Radicado

log = structlog.get_logger(__name__)

_IMAGEN_CARGADA = (
    "const img = document.getElementById('imagen-estado');"
    "return !!img && img.complete && img.naturalWidth > 0;"
)
_CAJA_EN_VIEWPORT = (
    "const img = document.getElementById('imagen-estado');"
    "img.scrollIntoView({block: 'center'});"
    "const r = img.getBoundingClientRect();"
    "return [r.x, r.y, r.width, r.height, window.devicePixelRatio];"
)


def crear_chrome(
    *, headless: bool = True, binario: str | None = None, chromedriver: str | None = None
) -> WebDriver:
    opciones = webdriver.ChromeOptions()
    if binario:
        opciones.binary_location = binario
    if headless:
        opciones.add_argument("--headless=new")
    for argumento in (
        "--window-size=1280,900",
        "--force-device-scale-factor=1",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--lang=es-CO",
    ):
        opciones.add_argument(argumento)
    servicio = ChromeService(executable_path=chromedriver) if chromedriver else None
    return webdriver.Chrome(options=opciones, service=servicio)


class PortalSelenium:
    """Implementa ``PortalConsultas``. Úsalo como context manager para cerrar el navegador."""

    def __init__(
        self,
        url_base: str,
        *,
        headless: bool = True,
        espera_s: float = 10.0,
        driver: WebDriver | None = None,
        binario: str | None = None,
        chromedriver: str | None = None,
    ) -> None:
        self._url_base = url_base.rstrip("/")
        self._espera_s = espera_s
        self._driver = driver or crear_chrome(
            headless=headless, binario=binario, chromedriver=chromedriver
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        self.cerrar()

    def cerrar(self) -> None:
        try:
            self._driver.quit()
        except WebDriverException:  # el navegador ya pudo haber muerto
            log.warning("No se pudo cerrar el navegador limpiamente")

    def obtener_imagen_estado(self, radicado: Radicado) -> Image.Image:
        try:
            return self._consultar(radicado)
        except (RadicadoInexistente, PortalNoDisponible):
            raise
        except TimeoutException as error:
            raise PortalNoDisponible(
                f"El portal no respondió en {self._espera_s:.0f} s para {radicado}"
            ) from error
        except WebDriverException as error:
            raise PortalNoDisponible(f"Fallo del navegador: {error.msg}") from error

    def _consultar(self, radicado: Radicado) -> Image.Image:
        espera = WebDriverWait(self._driver, self._espera_s)
        self._driver.get(f"{self._url_base}/")
        self._verificar_disponible()

        campo = espera.until(ec.element_to_be_clickable((By.ID, "radicado")))
        campo.clear()
        campo.send_keys(radicado.valor)
        self._driver.find_element(By.ID, "boton-consultar").click()

        espera.until(
            ec.any_of(
                ec.presence_of_element_located((By.ID, "imagen-estado")),
                ec.presence_of_element_located((By.ID, "mensaje-error")),
                ec.presence_of_element_located((By.ID, "fuera-de-servicio")),
            )
        )
        self._verificar_disponible()
        errores = self._driver.find_elements(By.ID, "mensaje-error")
        if errores:
            raise RadicadoInexistente(errores[0].text.strip())

        espera.until(lambda d: bool(d.execute_script(_IMAGEN_CARGADA)))
        x, y, ancho, alto, escala = self._ejecutar(_CAJA_EN_VIEWPORT)
        captura = self._driver.get_screenshot_as_png()
        return recortar(captura, Caja(x, y, ancho, alto), escala)

    def _verificar_disponible(self) -> None:
        if self._driver.find_elements(By.ID, "fuera-de-servicio"):
            raise PortalNoDisponible("El portal respondió 'servicio no disponible'")

    def _ejecutar(self, script: str) -> list[float]:
        resultado: Any = self._driver.execute_script(script)
        return [float(v) for v in resultado]
