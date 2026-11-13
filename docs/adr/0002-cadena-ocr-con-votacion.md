# ADR-0002 · Cadena de varios motores OCR con votación ponderada

- **Estado:** aceptada
- **Fecha:** 2026-11

## Contexto

Ningún motor OCR lee bien todas las imágenes ruidosas. Cada uno falla distinto:

- **ddddocr** (modelo ONNX entrenado con texto corto y deformado) es rápido y tolera bien la
  rotación de caracteres, pero confunde pares como `8/B` o `0/O`.
- **Tesseract** está pensado para documentos: con texto rotado y líneas cruzadas casi no lee,
  pero cuando lee una imagen limpia, rara vez inventa.
- **EasyOCR** (CRNN sobre PyTorch) es el más lento y pesado, y acierta en casos donde los
  otros dos fallan.

Además, ninguna variante de preprocesado sirve para todas las imágenes: la binarización que
limpia un fondo con manchas puede borrar un carácter tenue.

## Decisión

1. Cada imagen se lee con el producto **motor × variante** (5 variantes por defecto: Otsu ×2 con
   apertura morfológica, Otsu ×2, canal mínimo, mediana y original).
2. Cada lectura se **normaliza por posición** (`O→0` donde va un dígito, `5→S` donde va una
   letra) y se **valida** (patrón + dígito de verificación, ver ADR-0003).
3. Solo votan las lecturas válidas. Gana el código con más peso, si lo respaldan al menos
   `min_acuerdo` lecturas (2 por defecto) y no empata con otro código válido.
4. Si no hay mayoría y no hay códigos válidos en conflicto, se vota **carácter por carácter**
   y el resultado se acepta solo si su dígito de verificación cuadra.
5. **Parada temprana**: los motores se ordenan del más rápido al más lento y la lectura se
   detiene en cuanto `min_acuerdo` lecturas válidas coinciden. En la mayoría de imágenes,
   EasyOCR nunca se ejecuta.

## Consecuencias

- El banco de evaluación (`docs/evaluacion.md`) mide el aporte de cada capa y, con la fila de
  ablación, cuánto aporta cada motor a la cadena final.
- El costo por imagen depende de la dificultad: las fáciles se resuelven con 2 lecturas de
  ddddocr; las difíciles recorren la cadena completa.
- Los pesos por motor existen (`LectorConsenso.desde_motores(pesos=...)`) pero el valor por
  defecto es 1 para todos: el banco no mostró una mejora que justifique afinarlos, y pesos
  afinados sobre datos sintéticos podrían no servir en un portal real.
