# legacy/streamlit/ — app Streamlit en producción (CONGELADA)

Esta app está desplegada en Streamlit Community Cloud desde `main` y se retirará cuando la web nueva (`web/` + `api/`) la sustituya (Fase 3).

## Reglas

- **Solo correcciones de bugs.** Ninguna funcionalidad nueva: va en `api/`/`web/`.
- Toda la lógica de negocio vive en `core/`. Si un bug está en la lógica, arréglalo en `core/` con su test, no aquí.
- No quites el shim de `sys.path` al principio de `app.py`: Streamlit Cloud no instala el workspace uv, solo `requirements.txt`.
- `requirements.txt` es **generado**: `./scripts/export-legacy-requirements.sh`. No editarlo a mano.
- Verificación: `./scripts/verify.sh --smoke` arranca la app con la demo (AppTest). El asistente móvil (<768 px) no se puede probar con AppTest: pruébalo a mano y dilo.
- Ejecutar en local (desde la raíz): `uv run streamlit run legacy/streamlit/app.py`. La config de tema está en `/.streamlit/config.toml` (raíz del repo).
