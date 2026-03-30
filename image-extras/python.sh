#!/bin/bash
# Install Python via uv
# Env: YOLO_PYTHON_VERSION (optional, default: latest stable)
set -eu

if [ "${YOLO_VERIFY:-}" = "1" ]; then
    YOLO_PYTHON_VERSION="3.12"
fi

# Install uv if not present
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

if [ -n "${YOLO_PYTHON_VERSION:-}" ]; then
    uv python install "$YOLO_PYTHON_VERSION"
else
    uv python install
fi

# Create python3 and python symlinks
PYTHON_BIN="$(uv python find ${YOLO_PYTHON_VERSION:+$YOLO_PYTHON_VERSION} 2>/dev/null)"
if [ -n "$PYTHON_BIN" ]; then
    mkdir -p "$HOME/.local/bin"
    ln -sf "$PYTHON_BIN" "$HOME/.local/bin/python3"
    ln -sf "$PYTHON_BIN" "$HOME/.local/bin/python"
fi

if [ "${YOLO_VERIFY:-}" = "1" ]; then
    python --version || { echo "FAIL: python not found"; exit 1; }
    python3 --version || { echo "FAIL: python3 not found"; exit 1; }
fi
