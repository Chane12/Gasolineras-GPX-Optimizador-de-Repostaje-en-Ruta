#!/usr/bin/env bash
# Regenera legacy/streamlit/requirements.txt desde uv.lock.
# Streamlit Community Cloud no entiende el workspace uv: instala este archivo y la app
# importa el motor desde core/src (ver el shim de sys.path en legacy/streamlit/app.py).
# El CI lo ejecuta y falla si el archivo commiteado no coincide.
#
# La línea "core/src" lleva una huella del código del core: cuando el core cambia, cambia
# este archivo y Streamlit Cloud reinstala y REINICIA la app. Sin ella, un despliegue podía
# dejar la app ejecutando el core viejo hasta un reinicio manual.
set -euo pipefail
cd "$(dirname "$0")/.."
out=legacy/streamlit/requirements.txt
core_hash=$(git ls-files -z core/src | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | cut -c1-16)
{
  echo "# GENERADO por scripts/export-legacy-requirements.sh — no editar a mano."
  echo "# core/src: ${core_hash} (si cambia, Streamlit Cloud reinicia la app con el core nuevo)"
  uv export --frozen --package gasolineras-streamlit --no-emit-workspace --no-hashes --no-dev --no-header
} > "$out"
echo "OK: $out"
