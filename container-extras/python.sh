#!/bin/bash
# Install Python via uv
# Usage: python.sh [version]
# Default: latest stable
set -eu

# Install uv if not present
if ! command -v uv &>/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

VERSION="${1:-}"
if [ -n "$VERSION" ]; then
  uv python install "$VERSION"
else
  uv python install
fi

# Create python3 and python symlinks
PYTHON_BIN="$(uv python find ${VERSION:+$VERSION} 2>/dev/null)"
if [ -n "$PYTHON_BIN" ]; then
  ln -sf "$PYTHON_BIN" "$HOME/.local/bin/python3"
  ln -sf "$PYTHON_BIN" "$HOME/.local/bin/python"
fi
