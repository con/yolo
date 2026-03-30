#!/bin/bash
# Install Playwright with Chromium
# Env: none required
set -eu

sudo apt-get install -y --no-install-recommends nodejs npm

# System deps (needs root)
sudo npx playwright install-deps chromium

sudo npm install -g playwright
npx playwright install chromium

if [ "${YOLO_VERIFY:-}" = "1" ]; then
    npx playwright --version || { echo "FAIL: playwright not found"; exit 1; }
fi
