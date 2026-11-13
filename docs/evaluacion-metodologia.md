# Metodología del banco de evaluación

Los números están en [`evaluacion.md`](evaluacion.md) (generado, no se edita a mano). Este
documento explica cómo se obtienen y qué **no** significan.

## Qué se mide

Sobre un lote sintético reproducible (500 imágenes, semilla `2026`):

| Capa | Qué cambia respecto a la anterior |
|---|---|
| 1. Motor solo | La imagen tal como la publica el portal; se acepta lo que el motor lea. Es el punto de partida de cualquier bot de OCR. |
| 2. Preprocesado | La mejor variante (`otsu_x2_apertura`) + normalización posicional. Sigue sin validar: el motor siempre "responde". |
| 3. Votación por motor | Las 5 variantes, votación entre ellas y validación por patrón y dígito de verificación. Aparece la columna "sin respuesta". |
| 4. Votación entre motores | Todas las combinaciones motor × variante votan juntas. Una sola imagen. |
| 5. Producción | La cadena tal como corre el bot: parada temprana y hasta 3 imágenes por radicado. |
| 6. Ablación | Producción quitando un motor a la vez: muestra cuánto aporta cada uno. |

Para cada fila se reportan tres porcentajes que suman 100 %:

- **Acierto**: el código entregado es el correcto.
- **Error silencioso**: se entregó un código equivocado. Es el peor caso: termina en la base
  de datos y nadie lo nota.
- **Sin respuesta**: la cadena reconoce que no hay consenso. El radicado queda pendiente.

## Cómo reproducirlo

```bash
make evaluar-docker               # los tres motores (Docker, ~15 min la primera vez)
make evaluar                      # solo los motores instalados en tu máquina
vigia evaluar --cantidad 200 --semilla 7 --motores ddddocr,tesseract
```

Con la misma semilla y las mismas versiones de librerías, el resultado es idéntico. Entre
versiones de Pillow o de los modelos OCR puede variar ligeramente; el informe registra las
versiones usadas.

## Qué no significan estos números

- **No son el acierto sobre un portal real.** Son el acierto sobre imágenes sintéticas
  diseñadas para parecerse a las de un portal público. Sirven para comparar capas y
  configuraciones entre sí, no para prometer un porcentaje en otro sitio.
- **La línea base fue calibrada.** La dificultad del generador se ajustó para que un motor
  con preprocesado básico quedara cerca del ≈65 % del caso real que inspira el proyecto
  ([ADR-0008](adr/0008-datos-sinteticos-y-banco-de-evaluacion.md)). El hallazgo no es "la
  línea base es 65 %" (eso se eligió), sino **cuánto sube desde ahí** cada capa.
- **El reintento de imagen depende del portal.** La capa 5 asume que el portal genera ruido
  nuevo en cada solicitud, como el ficticio. Contra un portal que siempre entregue la misma
  imagen, el techo es la capa 4.
- **Riesgo de sobreajuste.** Las variantes se diseñaron mirando estas imágenes (con la semilla
  7); el banco usa otra semilla (2026), pero el tipo de ruido es el mismo.

## Para usarlo con un portal real

1. Guardar 200–500 imágenes del portal con el bot (el recorte es el mismo).
2. Etiquetarlas a mano (nombre del archivo = código correcto, como hace `vigia muestras`).
3. Adaptar el banco para leer esa carpeta en lugar del generador (el resto no cambia).
4. Decidir `min_acuerdo`, variantes y motores con esos números, no con los sintéticos.
