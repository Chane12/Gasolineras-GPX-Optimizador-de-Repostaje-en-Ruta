#!/usr/bin/env bash
# Regenera legacy/streamlit/requirements.txt desde uv.lock.
# Streamlit Community Cloud no entiende el workspace uv: instala este archivo y la app
# importa el motor desde core/src (ver el shim de sys.path en legacy/streamlit/app.py).
# El CI lo ejecuta y falla si el archivo commiteado no coincide.
set -euo pipefail
cd "$(dirname "$0")/.."
out=legacy/streamlit/requirements.txt
{
  echo "# GENERADO por scripts/export-legacy-requirements.sh — no editar a mano."
  uv export --frozen --package gasolineras-streamlit --no-emit-workspace --no-hashes --no-dev --no-header
} > "$out"
echo "OK: $out"
