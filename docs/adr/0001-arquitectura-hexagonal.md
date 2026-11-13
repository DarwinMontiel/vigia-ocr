# ADR-0001 · Arquitectura hexagonal (puertos y adaptadores)

- **Estado:** aceptada
- **Fecha:** 2026-11

## Contexto

Un bot de OCR sobre un portal público cambia por fuera más que por dentro: el portal rediseña
su HTML, aparece un motor OCR mejor, la base de datos pasa de SQLite a SQL Server, el
navegador se actualiza. Las reglas de negocio (qué es un código válido, cuándo una lectura es
confiable, cuándo no se vuelve a consultar) casi no cambian.

Si las reglas viven mezcladas con Selenium y SQLAlchemy, cada cambio externo obliga a
re-probar todo con navegador y base de datos reales, y las pruebas se vuelven lentas y frágiles.

## Decisión

Separar el código en tres anillos:

| Anillo | Paquete | Depende de |
|---|---|---|
| Dominio | `dominio/` | Nada (solo la biblioteca estándar) |
| Aplicación | `aplicacion/` + contratos en `puertos/` | Dominio y puertos (y Pillow como tipo de imagen) |
| Adaptadores | `adaptadores/`, `portal_ficticio/`, `cli.py` | Todo lo anterior y la infraestructura |

Los **puertos** son `typing.Protocol`: `MotorOCR`, `Preprocesador`, `PortalConsultas`,
`RepositorioResultados` y `Reloj`. La única pieza que conoce a la vez el núcleo y los
adaptadores es la raíz de composición (`contenedor.py`).

La regla no queda en un documento: `tests/unitarias/test_arquitectura.py` analiza los
`import` con `ast` y falla si el dominio o la aplicación importan Selenium, SQLAlchemy,
OpenCV, un motor OCR o un adaptador.

## Consecuencias

- Las 140+ pruebas del núcleo corren en ~3 s, sin navegador, sin base de datos y sin motores.
- Agregar un motor (p. ej. PaddleOCR) es escribir una clase con `nombre` y `leer()` y
  registrarla en `adaptadores/ocr/__init__.py`. El núcleo no cambia.
- Concesión pragmática: los puertos usan `PIL.Image.Image` como tipo de intercambio. Definir
  un tipo de imagen propio no aportaba nada y obligaba a convertir en cada adaptador. El
  dominio sí está libre de Pillow (también lo verifica la prueba de arquitectura).
- Hay más archivos que en un script único. Es el precio de poder cambiar una pieza sin miedo.
