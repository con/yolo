#!/bin/bash
# Install Jujutsu (jj) from GitHub releases
# Env: YOLO_JJ_VERSION (required)
set -eu

if [ "${YOLO_VERIFY:-}" = "1" ]; then
    YOLO_JJ_VERSION="0.38.0"
else
    [ -z "${YOLO_JJ_VERSION:-}" ] && { echo "jj.sh: YOLO_JJ_VERSION required"; exit 1; }
fi

ARCH=$(uname -m)
wget -qO /tmp/jj.tar.gz "https://github.com/jj-vcs/jj/releases/download/v${YOLO_JJ_VERSION}/jj-v${YOLO_JJ_VERSION}-${ARCH}-unknown-linux-musl.tar.gz"
mkdir -p ~/.local/bin
tar -xzf /tmp/jj.tar.gz -C ~/.local/bin ./jj
rm /tmp/jj.tar.gz

# zsh completions
if command -v zsh &>/dev/null; then
    mkdir -p ~/.zfunc
    ~/.local/bin/jj util completion zsh > ~/.zfunc/_jj
fi

if [ "${YOLO_VERIFY:-}" = "1" ]; then
    jj version || { echo "FAIL: jj not found"; exit 1; }
fi
