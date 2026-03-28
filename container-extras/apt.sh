#!/bin/bash
# Install apt packages
# Usage: apt.sh package1 package2 ...
set -eu
sudo apt-get install -y --no-install-recommends "$@"
