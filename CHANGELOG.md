# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y
[SemVer](https://semver.org/lang/es/).

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
