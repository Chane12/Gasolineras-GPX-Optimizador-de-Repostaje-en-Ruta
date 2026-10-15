# core/ — motor `gasolineras_core`

Mapa de módulos y flujo del pipeline: `core/README.md`.

## Reglas

- Es la pieza más crítica: **cualquier cambio de comportamiento necesita un test** que lo fije (en `core/tests/`). Si cambias un resultado a propósito, actualiza el test y explica el porqué en el commit.
- Funciones puras siempre que se pueda: separa la E/S (red, disco) de la lógica (ejemplo: `fetch_gasolineras` descarga, `parse_miteco_records` limpia). La lógica pura se testea sin mocks.
- Nada de `import streamlit`, `fastapi` ni nada de UI aquí. `visualization/folium_map.py` es una excepción heredada (la usan Streamlit y la CLI); no añadas más.
- Constantes y URLs en `config.py`. Rutas de datos: `DEMO_GPX_PATH` (empaquetado) y `DATA_DIR` (runtime, `GASOLINERAS_DATA_DIR`).
- Red: siempre `timeout=`; ante fallo, devolver `None`/fallback y dejar que la capa superior decida. Los tests simulan `requests.get` con `monkeypatch` (ver `tests/test_miteco.py`).
- Fixtures de test en `core/tests/fixtures/` (`.gitignore` las permite explícitamente). Snapshot del MITECO: `miteco_sample.json`.
- `print()` se usa como log en el código heredado; en código nuevo usa `logging.getLogger(__name__)`.
