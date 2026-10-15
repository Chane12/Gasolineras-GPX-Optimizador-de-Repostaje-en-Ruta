---
name: verificar
description: Verifica que el repo está en verde (lint, formato, tipos, tests, requirements legacy) y, si se tocó la app Streamlit, la arranca con la demo. Úsala SIEMPRE antes de dar una tarea por terminada, antes de commitear o de abrir un PR, y cuando el usuario pregunte si algo funciona.
---

# Verificar

Una tarea no está terminada hasta que esto pasa. No resumas resultados que no has visto.

## Pasos

1. Ejecuta la verificación completa desde la raíz del repo:
   ```bash
   ./scripts/verify.sh
   ```
2. Si el cambio toca `legacy/streamlit/` o algo que la app usa (casi todo `core/`), añade el smoke test (usa red, ~30 s):
   ```bash
   ./scripts/verify.sh --smoke
   ```
3. Si algún paso falla:
   - Lee el error completo; arregla la **causa**, no el síntoma (no silencies con `# noqa`, `# type: ignore` ni `pytest.skip` salvo que esté justificado y lo expliques).
   - `requirements.txt` desactualizado → `./scripts/export-legacy-requirements.sh` y commitea el resultado.
   - Vuelve a ejecutar hasta que todo esté en verde.
4. Revisa lo que no cubren las herramientas:
   - ¿Hay un test para la lógica nueva o para el bug corregido?
   - ¿`docs/ROADMAP.md` refleja el cambio (tarea marcada, deuda nueva anotada)?
   - ¿La decisión merece un ADR en `docs/decisions/`?

## Cómo informar

- Di exactamente qué se ejecutó y su resultado (p. ej. "32 tests en verde, pyright 0 errores, smoke OK").
- Di explícitamente lo que **no** se pudo verificar: vista móvil (<768 px) de Streamlit, comportamiento en producción, servicios externos caídos. No lo des por bueno.
