#!/bin/bash
# Install git-delta from GitHub releases
# Env: YOLO_GIT_DELTA_VERSION (required)
# TODO: determine latest from GitHub API if version not provided
set -eu
[ -z "${YOLO_GIT_DELTA_VERSION:-}" ] && { echo "git-delta.sh: YOLO_GIT_DELTA_VERSION required"; exit 1; }

ARCH=$(dpkg --print-architecture)
wget -q "https://github.com/dandavison/delta/releases/download/${YOLO_GIT_DELTA_VERSION}/git-delta_${YOLO_GIT_DELTA_VERSION}_${ARCH}.deb"
sudo dpkg -i "git-delta_${YOLO_GIT_DELTA_VERSION}_${ARCH}.deb"
rm "git-delta_${YOLO_GIT_DELTA_VERSION}_${ARCH}.deb"
