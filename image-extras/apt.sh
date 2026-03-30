#!/bin/bash
# Install apt packages
# Env: YOLO_APT_PACKAGES (space-separated, required)
set -eu

if [ "${YOLO_VERIFY:-}" = "1" ]; then
    YOLO_APT_PACKAGES="figlet"
else
    [ -z "${YOLO_APT_PACKAGES:-}" ] && { echo "apt.sh: YOLO_APT_PACKAGES required"; exit 1; }
fi

# shellcheck disable=SC2086  # intentional word splitting
sudo apt-get install -y --no-install-recommends $YOLO_APT_PACKAGES

if [ "${YOLO_VERIFY:-}" = "1" ]; then
    command -v figlet || { echo "FAIL: figlet not found after install"; exit 1; }
fi
