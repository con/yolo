#!/bin/bash
# Install git-delta from GitHub releases
# Env: YOLO_GIT_DELTA_VERSION (required)
set -eu

if [ "${YOLO_VERIFY:-}" = "1" ]; then
    YOLO_GIT_DELTA_VERSION="0.18.2"
else
    [ -z "${YOLO_GIT_DELTA_VERSION:-}" ] && { echo "git-delta.sh: YOLO_GIT_DELTA_VERSION required"; exit 1; }
fi

ARCH=$(dpkg --print-architecture)
wget -q "https://github.com/dandavison/delta/releases/download/${YOLO_GIT_DELTA_VERSION}/git-delta_${YOLO_GIT_DELTA_VERSION}_${ARCH}.deb"
sudo dpkg -i "git-delta_${YOLO_GIT_DELTA_VERSION}_${ARCH}.deb"
rm "git-delta_${YOLO_GIT_DELTA_VERSION}_${ARCH}.deb"

if [ "${YOLO_VERIFY:-}" = "1" ]; then
    delta --version || { echo "FAIL: delta not found"; exit 1; }
fi
