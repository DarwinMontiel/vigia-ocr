# Evaluación de la cadena OCR

> Archivo generado por `vigia evaluar` (no editar a mano). Los números son los que midió esta ejecución.

- **Muestras:** 500 imágenes sintéticas, semilla `2026` (reproducible).
- **Motores evaluados:** ddddocr, tesseract, easyocr
- **Variantes de preprocesado:** `otsu_x2_apertura`, `otsu_x2`, `canal_minimo`, `mediana`, `original`
- **Generado:** 2026-11-12T22:53:41+00:00

| Capa | Configuración | Acierto | Error silencioso | Sin respuesta | Imágenes/caso | Lecturas/caso |
|---|---|--:|--:|--:|--:|--:|
| 1. Motor solo | ddddocr · imagen cruda, sin validar | **48,6 %** | 51,4 % | 0,0 % | 1,00 | 1,00 |
| 1. Motor solo | tesseract · imagen cruda, sin validar | **0,2 %** | 3,6 % | 96,2 % | 1,00 | 1,00 |
| 1. Motor solo | easyocr · imagen cruda, sin validar | **24,2 %** | 74,6 % | 1,2 % | 1,00 | 1,00 |
| 2. Preprocesado | ddddocr · otsu_x2_apertura + normalización | **65,6 %** | 34,4 % | 0,0 % | 1,00 | 1,00 |
| 2. Preprocesado | tesseract · otsu_x2_apertura + normalización | **1,2 %** | 27,0 % | 71,8 % | 1,00 | 1,00 |
| 2. Preprocesado | easyocr · otsu_x2_apertura + normalización | **25,8 %** | 73,8 % | 0,4 % | 1,00 | 1,00 |
| 3. Votación por motor | ddddocr · 5 variantes + votación + DV | **74,0 %** | 0,2 % | 25,8 % | 1,00 | 5,00 |
| 3. Votación por motor | tesseract · 5 variantes + votación + DV | **1,2 %** | 0,0 % | 98,8 % | 1,00 | 5,00 |
| 3. Votación por motor | easyocr · 5 variantes + votación + DV | **43,0 %** | 0,6 % | 56,4 % | 1,00 | 5,00 |
| 4. Votación entre motores | ddddocr + tesseract + easyocr · votación + DV | **82,6 %** | 0,6 % | 16,8 % | 1,00 | 15,00 |
| 5. Producción | Producción · votación + DV + hasta 3 imágenes | **98,2 %** | 0,6 % | 1,2 % | 1,21 | 9,21 |
| 6. Ablación | Producción sin ddddocr | **81,2 %** | 1,2 % | 17,6 % | 1,89 | 16,97 |
| 6. Ablación | Producción sin tesseract | **98,2 %** | 0,6 % | 1,2 % | 1,22 | 6,39 |
| 6. Ablación | Producción sin easyocr | **95,8 %** | 0,2 % | 4,0 % | 1,35 | 7,90 |

**Cómo leer la tabla.** *Acierto*: el código entregado es el correcto. *Error silencioso*: se entregó un código equivocado (es el peor caso: termina en la base de datos). *Sin respuesta*: la cadena reconoce que no hay consenso y el radicado queda pendiente para la siguiente corrida. Las tres columnas suman 100 %.

## Costo por lectura

| Motor | ms promedio por lectura |
|---|--:|
| ddddocr | 11,5 |
| tesseract | 89,0 |
| easyocr | 118,8 |

## Entorno

| Componente | Versión |
|---|---|
| python | 3.13.18 |
| sistema | Linux x86_64 |
| pillow | 13.0.0 |
| opencv | 5.0.0.93 |
| ddddocr | 1.6.1 |
| pytesseract | 0.3.13 |
| easyocr | 1.7.2 |
| tesseract | 5.5.0 |
