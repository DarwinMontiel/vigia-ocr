# Política de seguridad

## Reportar una vulnerabilidad

No abras un issue público. Usa **Security → Report a vulnerability** en este repositorio
(GitHub Private Vulnerability Reporting). Recibirás respuesta en un máximo de 5 días hábiles.

## Prácticas del proyecto

- Secretos solo por variables de entorno; `.env` está en `.gitignore`. La cadena de conexión
  nunca se escribe en los logs (el CLI solo muestra el servidor).
- Dependabot mantiene actualizadas las dependencias de Python, Docker y GitHub Actions.
- Ruff ejecuta las reglas de seguridad de Bandit (`S`) en cada commit y en CI.
- La imagen Docker corre con un usuario sin privilegios (`vigia`, UID 10001).
- El portal ficticio escapa todo dato que muestra en HTML.

## Uso responsable

Vigía OCR consulta portales **públicos** como lo haría una persona: un radicado a la vez, sin
paralelismo agresivo, con un circuit breaker que deja de consultar cuando el portal falla.
No incluye ni debe incluir mecanismos para eludir controles de acceso, autenticación o
límites de uso de un sitio. Antes de automatizar un portal real, revisa sus términos de uso.
