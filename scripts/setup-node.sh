#!/usr/bin/env bash
# Instala en .tools/node la versión de Node fijada en .node-version y el pnpm de web/package.json
# ("packageManager"), sin tocar el Node del sistema. Idempotente: si ya está, no hace nada.
# Descarga de nodejs.org y comprueba la suma SHA-256 oficial antes de descomprimir.
#   ./scripts/setup-node.sh        → instala (o confirma) Node y pnpm
#   ./scripts/pnpm <args>           → ejecuta pnpm con ese Node (p. ej. ./scripts/pnpm -C web dev)
set -euo pipefail
cd "$(dirname "$0")/.."

node_version="$(tr -d '[:space:]' < .node-version)"
pnpm_version="$(python3 -c 'import json; print(json.load(open("web/package.json"))["packageManager"].split("@")[1])')"
tools=".tools"
node_dir="$tools/node-v$node_version"

if [[ -x "$node_dir/bin/node" && -x "$node_dir/bin/pnpm" ]] \
  && [[ "$("$node_dir/bin/pnpm" --version)" == "$pnpm_version" ]]; then
  ln -sfn "node-v$node_version" "$tools/node"
  exit 0
fi

case "$(uname -s)" in
  Linux) os=linux ;;
  Darwin) os=darwin ;;
  *) echo "✗ Sistema no soportado: $(uname -s)"; exit 1 ;;
esac
case "$(uname -m)" in
  x86_64 | amd64) arch=x64 ;;
  aarch64 | arm64) arch=arm64 ;;
  *) echo "✗ Arquitectura no soportada: $(uname -m)"; exit 1 ;;
esac

if [[ ! -x "$node_dir/bin/node" ]]; then
  name="node-v$node_version-$os-$arch"
  base="https://nodejs.org/dist/v$node_version"
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  echo "▶ Descargando Node $node_version ($os-$arch)…"
  curl -fsSL --retry 3 -o "$tmp/$name.tar.xz" "$base/$name.tar.xz"
  curl -fsSL --retry 3 -o "$tmp/SHASUMS256.txt" "$base/SHASUMS256.txt"
  expected="$(grep " $name.tar.xz\$" "$tmp/SHASUMS256.txt" | cut -d' ' -f1)"
  if command -v sha256sum >/dev/null; then
    actual="$(sha256sum "$tmp/$name.tar.xz" | cut -d' ' -f1)"
  else
    actual="$(shasum -a 256 "$tmp/$name.tar.xz" | cut -d' ' -f1)"
  fi
  if [[ -z "$expected" || "$expected" != "$actual" ]]; then
    echo "✗ La suma SHA-256 de Node no coincide; no se instala."
    exit 1
  fi
  mkdir -p "$tools"
  tar -xJf "$tmp/$name.tar.xz" -C "$tmp"
  rm -rf "$node_dir"
  mv "$tmp/$name" "$node_dir"
fi

echo "▶ Instalando pnpm $pnpm_version…"
PATH="$PWD/$node_dir/bin:$PATH" "$node_dir/bin/npm" install --global --silent --no-fund --no-audit \
  --prefix "$node_dir" "pnpm@$pnpm_version"
ln -sfn "node-v$node_version" "$tools/node"
echo "✔ Node $("$node_dir/bin/node" --version) y pnpm $("$node_dir/bin/pnpm" --version) en $tools/node"
