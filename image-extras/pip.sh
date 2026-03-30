#!/bin/bash
# Install pip packages via uv tool
# Env: YOLO_PIP_PACKAGES (space-separated, required)
set -eu

if [ "${YOLO_VERIFY:-}" = "1" ]; then
    YOLO_PIP_PACKAGES="cowsay"
else
    [ -z "${YOLO_PIP_PACKAGES:-}" ] && { echo "pip.sh: YOLO_PIP_PACKAGES required"; exit 1; }
fi

if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# shellcheck disable=SC2086  # intentional word splitting
for pkg in $YOLO_PIP_PACKAGES; do
    uv tool install "$pkg"
done
uv cache clean

if [ "${YOLO_VERIFY:-}" = "1" ]; then
    command -v cowsay || { echo "FAIL: cowsay not found after install"; exit 1; }
fi
