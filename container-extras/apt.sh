#!/bin/bash
# Install apt packages
# Env: YOLO_APT_PACKAGES (space-separated, required)
set -eu
[ -z "${YOLO_APT_PACKAGES:-}" ] && { echo "apt.sh: YOLO_APT_PACKAGES required"; exit 1; }
sudo apt-get install -y --no-install-recommends $YOLO_APT_PACKAGES
