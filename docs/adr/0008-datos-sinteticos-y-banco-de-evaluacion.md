# ADR-0008 · Datos sintéticos con semilla y banco de evaluación

- **Estado:** aceptada
- **Fecha:** 2026-11

## Contexto

"El OCR mejoró" no es una afirmación verificable. Hace falta medir, con las mismas
imágenes, cada cambio de la cadena. Y en un repositorio público no se pueden usar imágenes
de un portal real.

## Decisión

- Un **generador sintético** (`sintetico/generador.py`) dibuja códigos con rotación por
  carácter, colores de tinta variables, fondo con ruido y manchas, líneas de interferencia del
  mismo color que el texto, puntos y una onda sinusoidal. Todo el azar sale de
  `random.Random(semilla)` y la fuente es la que trae Pillow, así que **la misma semilla
  produce la misma imagen en cualquier máquina**.
- El **mismo generador** alimenta al portal ficticio y al banco: lo medido es lo que el bot
  enfrenta en la demo.
- El **banco** (`vigia evaluar`) ejecuta el código de producción (no una copia) y reporta,
  para cada capa, acierto, error silencioso y sin respuesta, además del costo por lectura y
  una ablación por motor. Escribe `docs/evaluacion.md` y `docs/evaluacion.json`.
- La dificultad del generador se calibró para que la **línea base** (un motor con
  preprocesado básico) quedara cerca del punto de partida del caso real que inspira el
  proyecto (≈65 %). Esa calibración es una decisión de diseño, no un resultado, y por eso se
  declara aquí: lo que el banco demuestra es cuánto sube el acierto *desde* esa línea base.

## Consecuencias

- Cualquier cambio de la cadena se acompaña de su antes y después en el PR.
- Los números son **sobre datos sintéticos**. Indican el aporte relativo de cada capa, no el
  acierto que tendrá el bot sobre otro portal; para eso hay que repetir la medición con una
  muestra etiquetada de ese portal (ver `docs/evaluacion-metodologia.md`).
- Riesgo de sobreajuste: las variantes y la normalización se diseñaron mirando estas
  imágenes. Para mitigarlo, el banco usa una semilla distinta (2026) a la que se usó
  durante el ajuste (7).
