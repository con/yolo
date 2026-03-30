#!/bin/bash
# Install DataLad with extensions via uv tool
# Env: none required
set -eu

if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

uv tool install --with datalad-container --with datalad-next datalad
uv cache clean

if [ "${YOLO_VERIFY:-}" = "1" ]; then
    datalad --version || { echo "FAIL: datalad not found"; exit 1; }
fi
