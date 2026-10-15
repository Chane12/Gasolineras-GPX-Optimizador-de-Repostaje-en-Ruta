#!/usr/bin/env bash
# PostToolUse (Edit|Write): formatea el archivo recién editado.
# Recibe el JSON del hook por stdin. Nunca bloquea: si algo falla, sale con 0.
set -uo pipefail
f=$(jq -r '.tool_response.filePath // .tool_input.file_path // empty')
[ -n "$f" ] && [ -f "$f" ] || exit 0
root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
case "$f" in
  "$root"/*.py)
    cd "$root" || exit 0
    uv run --no-sync ruff format --quiet "$f"
    uv run --no-sync ruff check --fix --quiet "$f" >/dev/null  # arregla imports/estilo; los avisos los ve el CI
    ;;
  "$root"/web/*.ts|"$root"/web/*.tsx|"$root"/web/*.js|"$root"/web/*.jsx|"$root"/web/*.css|"$root"/web/*.json)
    # Fase 2: prettier del proyecto web (solo si ya existe)
    [ -x "$root/web/node_modules/.bin/prettier" ] && "$root/web/node_modules/.bin/prettier" --write --log-level warn "$f"
    ;;
esac
exit 0
