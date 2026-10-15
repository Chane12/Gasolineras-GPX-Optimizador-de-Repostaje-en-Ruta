#!/usr/bin/env bash
# Regenera api/openapi.json: el contrato de la API, del que la web genera sus tipos (ADR 0001).
# El CI lo ejecuta y falla si el archivo commiteado no coincide: así cada cambio de contrato se ve en el PR.
set -euo pipefail
cd "$(dirname "$0")/.."
out=api/openapi.json
uv run python - "$out" <<'PY'
import json
import sys

from gasolineras_api.main import create_app

with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(create_app(warm_up=False).openapi(), f, ensure_ascii=False, indent=2, sort_keys=True)
    f.write("\n")
PY
echo "OK: $out"
