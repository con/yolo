#!/bin/bash
# Install apt packages
# Env: YOLO_APT_PACKAGES (space-separated, required)
set -eu
[ -z "${YOLO_APT_PACKAGES:-}" ] && { echo "apt.sh: YOLO_APT_PACKAGES required"; exit 1; }
# shellcheck disable=SC2086  # intentional word splitting
sudo apt-get install -y --no-install-recommends $YOLO_APT_PACKAGES
