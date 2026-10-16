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
  "$root"/web/*.ts|"$root"/web/*.tsx|"$root"/web/*.mts|"$root"/web/*.js|"$root"/web/*.mjs|"$root"/web/*.jsx|"$root"/web/*.css|"$root"/web/*.json|"$root"/web/*.md)
    # Web: prettier con el Node del proyecto (.tools/node), solo si ya están instalados
    [ -x "$root/web/node_modules/.bin/prettier" ] && [ -x "$root/.tools/node/bin/node" ] \
      && PATH="$root/.tools/node/bin:$PATH" "$root/web/node_modules/.bin/prettier" --write --log-level warn "$f"
    ;;
esac
exit 0
