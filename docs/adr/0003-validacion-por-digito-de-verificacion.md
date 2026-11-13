# ADR-0003 · Validación por patrón y dígito de verificación

- **Estado:** aceptada
- **Fecha:** 2026-11

## Contexto

Un OCR que se equivoca en un solo carácter produce un código que *parece* correcto. Si ese
código se guarda, nadie lo nota hasta que una gestión de cobranza se hace sobre un estado
falso (por ejemplo, insistir en el cobro de una obligación que ya tiene acuerdo de pago).

## Decisión

El código de estado tiene estructura fija: `EE` (estado) + 5 dígitos de serie + 1 dígito de
verificación **Luhn** (mod 10) sobre la serie. Toda lectura se valida contra:

1. el patrón `^(AC|AP|EM|SU|TE)\d{6}$`, y
2. el dígito de verificación.

Se eligió Luhn porque detecta el **100 % de los errores de un solo dígito** y casi todas las
transposiciones de dígitos adyacentes (no detecta `09↔90`), que son justo los errores típicos
de un OCR. Ambas propiedades están cubiertas por pruebas (`test_codigo.py`).

En un portal real el dígito de verificación puede no existir. En ese caso la validación se
apoya en lo que sí haya: el patrón del radicado, un catálogo cerrado de estados, o el
cruce con el estado anterior conocido (un proceso terminado no vuelve a "activo").

## Consecuencias

- La validación convierte errores silenciosos en "sin respuesta", que se reintentan.
- La votación por carácter (ADR-0002) solo es segura gracias al DV: mezclar caracteres de
  varias lecturas sin un árbitro independiente sería inventar un código.
- La probabilidad de que una lectura aleatoria pase el DV es 1/10; por eso además se exige
  acuerdo de al menos dos lecturas.
