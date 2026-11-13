# Guía de contribución

## Flujo de trabajo

1. Crear una rama desde `main`: `feat/<tema>`, `fix/<tema>` o `docs/<tema>`.
2. Instalar el entorno: `make install` (paquete editable, motores livianos y *hooks* de
   pre-commit). Para EasyOCR: `make install-completo`.
3. Hacer commits pequeños con [Conventional Commits](https://www.conventionalcommits.org/es/)
   y mensajes en español: `feat(ocr): …`, `fix(portal): …`, `docs(adr): …`, `test: …`.
4. Antes de abrir el PR: `make lint test` en verde, y `make test-ocr e2e` si el cambio toca
   motores, preprocesado, el portal o Selenium.
5. El PR explica el **qué** y el **por qué**, y enlaza el issue.

## Estándares

- `mypy --strict` y `ruff` sin advertencias (incluye reglas de seguridad de Bandit).
- El núcleo (`dominio/`, `aplicacion/`, `puertos/`) no importa infraestructura; la prueba de
  arquitectura lo hace cumplir.
- Toda regla nueva lleva prueba unitaria con dobles; nada de servicios reales en `make test`.
- Textos para humanos (logs, errores, documentación, commits) en español.
- Todo dato de ejemplo es ficticio y debe notarse que lo es.
- Las decisiones de arquitectura se documentan como ADR en `docs/adr/`.

## Cambios en la cadena OCR

Cualquier cambio en variantes, normalización, votación o motores debe acompañarse de su
**antes y después** del banco de evaluación:

```bash
git stash && make evaluar && cp docs/evaluacion.md /tmp/antes.md && git stash pop
make evaluar && diff /tmp/antes.md docs/evaluacion.md
```

Un cambio que suba el acierto a costa de introducir **errores silenciosos** no se acepta.

## Agregar un motor OCR

1. Crear `src/vigia_ocr/adaptadores/ocr/<motor>_motor.py` con una clase que tenga `nombre` y
   `leer(imagen) -> str`, e importe su librería dentro de `__init__` (import perezoso).
2. Traducir "no instalado" y fallas de inicialización a `MotorNoDisponible`.
3. Registrarlo en `FABRICAS` (`adaptadores/ocr/__init__.py`) y, si es opcional, como extra en
   `pyproject.toml`.
4. Correr el banco y documentar su aporte (la fila de ablación lo muestra).
