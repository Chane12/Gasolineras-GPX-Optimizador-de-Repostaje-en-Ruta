# 0003 — Monorepo con workspace uv y `core` sin UI

- **Estado**: Aceptada
- **Fecha**: 2026-10-15

## Contexto

Van a convivir varias piezas: el motor, la app Streamlit (en producción hasta el lanzamiento), una API y una web. Antes todo estaba en la raíz (`src/`, `app.py`, `main.py`) con un único `pyproject.toml`. Programar con IA exige límites claros: cada pieza debe poder cambiarse sin romper las demás.

## Decisión

- **Un solo repositorio** con carpetas por pieza: `core/`, `legacy/streamlit/`, y más adelante `api/` y `web/`.
- **Workspace uv** para las piezas Python: cada una con su `pyproject.toml` y un único `uv.lock` compartido. La raíz no es un paquete.
- **`core` no depende de ninguna interfaz** (ni Streamlit ni FastAPI). Las interfaces dependen de `core`, nunca al revés.
- **Streamlit Cloud** no entiende el workspace: instala `legacy/streamlit/requirements.txt` (generado desde `uv.lock` por `scripts/export-legacy-requirements.sh`, comprobado por el CI) y la app importa el core desde `core/src` mediante un shim de `sys.path`.

## Alternativas consideradas

- **Varios repositorios**: más coordinación, versiones cruzadas y contexto partido para la IA.
- **Un único paquete Python con extras**: mezcla dependencias de UI con el motor y la API acabaría instalando Streamlit.
- **Instalar el core en Streamlit Cloud mediante una ruta local en `requirements.txt`**: depende del directorio desde el que Streamlit Cloud ejecute pip, que no está documentado; el shim es más robusto.

## Consecuencias

- `uv sync --all-packages` instala todo; los tests y el linter se configuran en la raíz.
- Mover `app.py` obligó a cambiar el archivo principal en Streamlit Cloud (acción manual, una sola vez).
- El shim de `sys.path` es deuda aceptada: desaparece al retirar Streamlit (Fase 3).
