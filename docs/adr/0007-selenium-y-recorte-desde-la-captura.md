# ADR-0007 · Selenium y recorte de la imagen desde la captura de pantalla

- **Estado:** aceptada
- **Fecha:** 2026-11

## Contexto

Hay dos formas de obtener la imagen del estado:

1. Leer el atributo `src` del `<img>` y descargarlo con HTTP.
2. Tomar una captura de pantalla del navegador y recortar el rectángulo del `<img>`.

En muchos portales la URL de la imagen lleva un *token* de un solo uso o depende de la
sesión: descargarla de nuevo devuelve otra imagen (con otro ruido) o un error. En el portal
ficticio ocurre lo primero, a propósito.

## Decisión

- Navegar con **Selenium + Chrome** (Selenium Manager resuelve `chromedriver`; en Docker se
  usan `chromium` y `chromium-driver` del sistema).
- Esperar explícitamente a que la imagen termine de cargar (`img.complete && naturalWidth > 0`),
  nunca con `sleep`.
- Llevar la imagen al centro de la vista, obtener su `getBoundingClientRect()` y
  `devicePixelRatio`, tomar la captura y **recortar con Pillow**. El recorte es una función
  pura (`adaptadores/portal/recorte.py`) con pruebas para escala 1× y 2× (pantallas HiDPI).
- Traducir los errores del navegador a errores del dominio: `TimeoutException` y
  `WebDriverException` → `PortalNoDisponible`; mensaje de "no existe" → `RadicadoInexistente`.

## Por qué Selenium y no Playwright

El resto del portafolio ya usa Playwright. Este proyecto usa Selenium a propósito: es la
herramienta que más se encuentra en bots RPA heredados y en entornos corporativos con
Windows, y vale la pena mostrar las buenas prácticas también ahí (esperas explícitas,
traducción de errores, cierre garantizado del navegador con *context manager*).

## Consecuencias

- Lo que el bot lee es exactamente lo que vería una persona.
- La captura depende del tamaño de ventana: se fija `--window-size=1280,900` y
  `--force-device-scale-factor=1`, y aun así el recorte corrige la escala si difiere.
