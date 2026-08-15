#!/usr/bin/env bash
# Buduje binarkę sidecara PyInstallerem i wkłada ją tam, gdzie oczekuje jej Tauri:
# src-tauri/binaries/tutor-sidecar-<target-triple>. Triple można nadpisać 1. argumentem.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRIPLE="${1:-$(rustc -Vv | awk '/^host:/ { print $2 }')}"

cd "$ROOT/sidecar"
uv sync --group build
uv run pyinstaller \
    --onefile \
    --noconfirm \
    --clean \
    --name tutor-sidecar \
    --paths . \
    --add-data "$ROOT/sidecar/tutor_sidecar/db/migrations:tutor_sidecar/db/migrations" \
    --distpath dist \
    --workpath build \
    --specpath build \
    tutor_sidecar/main.py

SUFFIX=""
[[ "$TRIPLE" == *windows* ]] && SUFFIX=".exe"

mkdir -p "$ROOT/src-tauri/binaries"
cp "dist/tutor-sidecar$SUFFIX" "$ROOT/src-tauri/binaries/tutor-sidecar-$TRIPLE$SUFFIX"
echo "OK → src-tauri/binaries/tutor-sidecar-$TRIPLE$SUFFIX"
