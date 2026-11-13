# ADR-0005 · Idempotencia por fecha de corte y verificación tras guardar

- **Estado:** aceptada
- **Fecha:** 2026-11

## Contexto

Los lotes se relanzan: porque el servidor se reinició, porque el portal se cayó a la mitad o
porque alguien ejecutó el bot dos veces. Además, en producción puede haber más de un bot
sobre la misma base de datos.

## Decisión

1. **Clave de idempotencia** = `(radicado, fecha_corte)`. Un radicado se consulta una sola
   vez por fecha de corte.
2. **Antes de consultar**, el caso de uso busca el resultado; si existe, el radicado se marca
   `omitido_ya_existia` y el portal ni se toca.
3. **La base de datos es la autoridad**: restricción `UNIQUE (radicado, fecha_corte)` en
   `vigia_resultados`. Si dos bots guardan a la vez, uno recibe `IntegrityError`, que el
   repositorio traduce en `guardar() → False`. Gana el primero.
4. **Verificación tras guardar**: después del `INSERT` se vuelve a leer el registro en una
   sesión nueva (sin caché del ORM) y se compara código y estado. Si no coinciden o el
   registro no aparece, se lanza `ErrorVerificacion` y el lote se detiene: algo anda mal en
   la base de datos (un *trigger*, una réplica, un truncamiento) y seguir sería acumular datos
   malos.
5. **Auditoría**: cada resultado guarda todas las lecturas de los motores en
   `vigia_lecturas`, para poder explicar cualquier estado a posteriori.

## Consecuencias

- Relanzar un lote es seguro y barato: solo se consultan los pendientes.
- La verificación cuesta una lectura extra por radicado; es despreciable frente a la
  navegación.
- El DDL de SQL Server (`sql/001_esquema.sql`) añade `CHECK` sobre estado, confianza e
  imágenes, y una vista `vigia_ultimo_estado` para operación.
