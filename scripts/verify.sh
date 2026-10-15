#!/usr/bin/env bash
# Verificación completa del repo. La ejecutan el CI, la skill /verificar y cualquiera antes de un PR.
#   ./scripts/verify.sh           → lint, formato, tipos, tests (sin red), requirements legacy y contrato OpenAPI al día
#   ./scripts/verify.sh --smoke   → además arranca la app Streamlit con la demo (usa red: MITECO)
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n\033[1;34m▶ %s\033[0m\n' "$1"; }

step "Lint (ruff check)";            uv run ruff check .
step "Formato (ruff format --check)"; uv run ruff format --check .
step "Tipos (pyright)";              uv run pyright
step "Tests (pytest, sin red)";      uv run pytest -q -m "not network"
step "requirements.txt legacy al día"
./scripts/export-legacy-requirements.sh >/dev/null
git diff --exit-code -- legacy/streamlit/requirements.txt \
  || { echo "✗ legacy/streamlit/requirements.txt desactualizado (cambiaron las dependencias o el core): commitea el archivo regenerado."; exit 1; }

step "Contrato OpenAPI al día (api/openapi.json)"
./scripts/export-openapi.sh >/dev/null
git diff --exit-code -- api/openapi.json \
  || { echo "✗ api/openapi.json desactualizado (cambió el contrato de la API): commitea el archivo regenerado y dilo en el PR."; exit 1; }

if [[ "${1:-}" == "--smoke" ]]; then
  step "Smoke test app Streamlit (demo, red)"
  uv run python scripts/smoke_legacy.py
fi

printf '\n\033[1;32m✔ Todo en verde\033[0m\n'
