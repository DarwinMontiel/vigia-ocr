# ADR-0004 · Sin consenso, pedir otra imagen en lugar de adivinar

- **Estado:** aceptada
- **Fecha:** 2026-11

## Contexto

El portal genera el ruido de la imagen en cada solicitud. Una imagen con una línea encima del
`8` puede ser ilegible, y la siguiente, legible. Repetir la consulta cuesta un par de
segundos; guardar un estado equivocado cuesta una gestión de cobranza mal hecha.

## Decisión

- Si la votación no alcanza consenso, el caso de uso pide **una imagen nueva** al portal,
  hasta `VIGIA_MAX_IMAGENES` (3 por defecto).
- Si tras ese máximo sigue sin consenso, el radicado termina como
  `sin_lectura_confiable`: **queda pendiente** para la siguiente corrida y el CLI sale con
  código 2. No se guarda nada.
- El informe del banco separa **error silencioso** (entregó un código equivocado) de
  **sin respuesta** (reconoció que no sabía). El objetivo de diseño es error silencioso 0 %.

## Consecuencias

- El acierto final depende del número de imágenes permitidas; el banco reporta cuántas
  imágenes se pidieron en promedio por caso, para que el costo sea visible.
- Contra un portal que *no* regenere la imagen, este mecanismo no sirve: habría que
  reintentar más tarde o variar el preprocesado. Documentado en el runbook.
- No se usa ningún servicio externo de resolución ni se intenta eludir controles del portal:
  el bot consulta como lo haría una persona, a un ritmo moderado.
