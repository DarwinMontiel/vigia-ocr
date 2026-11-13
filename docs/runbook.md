# Runbook de operación

Guía para quien opera el bot. Cada sección empieza por el síntoma que se ve en los logs o en
el resumen del lote.

## Códigos de salida de `vigia consultar`

| Código | Significado | Acción |
|---|---|---|
| 0 | Todos los radicados tienen estado confirmado (o son inexistentes) | Ninguna |
| 2 | Quedaron radicados pendientes (`sin_lectura_confiable`, `portal_no_disponible`, `circuito_abierto`) | Volver a ejecutar más tarde: la idempotencia garantiza que solo se consultan los pendientes |
| 1 | Error inesperado (configuración, base de datos, `ErrorVerificacion`) | Revisar el log; no relanzar a ciegas |

## `circuito_abierto` en varios radicados seguidos

El portal falló `VIGIA_BREAKER_UMBRAL_FALLOS` veces seguidas y el bot dejó de consultarlo.

1. Abrir el portal en un navegador. Si responde "servicio no disponible", esperar.
2. Relanzar el lote: los radicados ya guardados se omiten.
3. Si el portal responde pero el bot sigue fallando, probablemente cambió el HTML: revisar que
   existan `#radicado`, `#boton-consultar` e `#imagen-estado` (o sus equivalentes) y ajustar
   `adaptadores/portal/selenium_portal.py`.

## Muchos `sin_lectura_confiable`

La cadena no logra consenso. No es un error: el bot prefirió no adivinar.

1. Tomar un radicado afectado y guardar la imagen. `vigia leer imagen.png` muestra qué leyó
   cada motor en cada variante.
2. Si todas las lecturas están vacías o cortadas, el recorte puede estar mal (cambió el
   tamaño o la posición de la imagen).
3. Si las lecturas son "casi" correctas, probar más imágenes (`VIGIA_MAX_IMAGENES=5`) o
   agregar EasyOCR (`pip install -e '.[easyocr]'`).
4. Medir antes de cambiar: `make evaluar` sobre una muestra etiquetada del portal.

## `ErrorVerificacion` (el lote se detuvo)

Lo que se leyó de la base de datos después de guardar no coincide con lo que se guardó.
**No relanzar** hasta entender la causa:

- ¿Hay *triggers* sobre `dbo.vigia_resultados`?
- ¿La cadena de conexión apunta a una réplica de solo lectura con retraso?
- ¿Alguien cambió el tamaño de una columna (truncamiento)?

## Tesseract no aparece

`Motor omitido ... No se encontró el binario de Tesseract`. Con
`VIGIA_OMITIR_MOTORES_NO_DISPONIBLES=true` (por defecto) el bot sigue con los demás motores.

- Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
- Windows: instalador de UB Mannheim y agregar `C:\Program Files\Tesseract-OCR` al `PATH`.

## Consultas útiles (SQL Server)

```sql
-- Estado más reciente de cada radicado
SELECT * FROM dbo.vigia_ultimo_estado ORDER BY radicado;

-- Lecturas que explican un resultado
SELECT l.motor, l.variante, l.texto_crudo, l.texto_normalizado, l.valido
FROM dbo.vigia_lecturas AS l
JOIN dbo.vigia_resultados AS r ON r.id = l.resultado_id
WHERE r.radicado = 'PCA-2026-00017' AND r.fecha_corte = '2026-11-12';

-- Resultados con confianza baja, para revisión humana
SELECT radicado, codigo, confianza, metodo FROM dbo.vigia_resultados
WHERE confianza < 0.5 ORDER BY confianza;
```
