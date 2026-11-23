# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y
[SemVer](https://semver.org/lang/es/).

## [Sin publicar]

### Corregido
- Demo web: cada caso muestra la imagen con el código de su propio expediente; antes el
  radicado y la nota del catálogo aparecían junto a un código al azar de otro estado.
- `vigia demo-web --motores` valida los nombres (y tolera espacios) en lugar de fallar más
  adelante con un error poco claro.
- `vigia consultar --fecha-corte` con una fecha mal escrita responde con un error de
  parámetro en lugar de una traza de Python.
- `vigia consultar` y `vigia db-crear` cierran las conexiones a la base de datos al terminar.
- README: el inicio rápido genera `muestras/` antes de `vigia leer muestras/*.png`.
- ADR-0002: la descripción de la parada temprana coincide con el orden real de lectura
  (por variante y, dentro de cada una, del motor más rápido al más lento).

## [1.0.0] - 2026-11-12

Primera versión pública.

### Agregado
- Núcleo hexagonal: dominio (código de estado con dígito Luhn, normalización posicional,
  votación ponderada), casos de uso (`ServicioConsulta`, `LectorConsenso`, `CircuitBreaker`) y
  puertos como `typing.Protocol`. Prueba de arquitectura que impide importar infraestructura
  desde el núcleo.
- Motores OCR intercambiables con import perezoso: ddddocr, Tesseract (pytesseract) y
  EasyOCR (extra opcional con PyTorch CPU).
- Cinco variantes de preprocesado con Pillow y OpenCV (escala de grises, canal mínimo,
  escalado, mediana, Otsu, apertura morfológica, filtro de componentes).
- Bot con Selenium + Chrome: esperas explícitas, recorte desde la captura con corrección de
  `devicePixelRatio` y traducción de errores del navegador a errores del dominio.
- Persistencia con SQLAlchemy: SQL Server (pyodbc) y SQLite; idempotencia por
  `(radicado, fecha_corte)` garantizada por la base de datos, verificación tras guardar y
  auditoría de lecturas. Script DDL idempotente para SQL Server con vista de último estado.
- Portal público ficticio (FastAPI) del Juzgado Promiscuo de Puerto Candela, con imagen de
  estado que cambia de ruido en cada solicitud y simulación de caídas.
- Generador de imágenes sintéticas con semilla y banco de evaluación (`vigia evaluar`) con
  capas, errores silenciosos, costo por lectura y ablación por motor.
- CLI `vigia` (typer): `portal`, `consultar`, `leer`, `muestras`, `evaluar`, `db-crear`,
  `demo-web`. Configuración con pydantic-settings y logs estructurados en español.
- Demo estática para GitHub Pages con lecturas reales de la cadena.
- CI: lint, tipos y unitarias en Python 3.11–3.13; OCR real; E2E con Chrome; SQL Server
  (opcional, requiere aceptar la licencia); imagen Docker con prueba de humo.
