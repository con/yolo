#!/bin/bash
# Test that container-extras build correctly and are idempotent
export PS4='> '
set -x
set -eu

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_CONTEXT="$(mktemp -d ${TMPDIR:-/tmp}/yolo-test-XXXXXXX)"
trap "rm -rf $BUILD_CONTEXT" EXIT

# Assemble build context
mkdir -p "$BUILD_CONTEXT/build/scripts"
cp "$REPO_ROOT/container-extras/apt.sh" "$BUILD_CONTEXT/build/scripts/"
cp "$REPO_ROOT/container-extras/python.sh" "$BUILD_CONTEXT/build/scripts/"
cat > "$BUILD_CONTEXT/build/run.sh" << 'EOF'
#!/bin/bash
set -eu
bash /tmp/yolo-build/scripts/apt.sh zsh fzf shellcheck
bash /tmp/yolo-build/scripts/python.sh 3.12
EOF

IMAGE="yolo-test-extras-$$"

# Build
podman build -f "$REPO_ROOT/images/Containerfile.extras" -t "$IMAGE" "$BUILD_CONTEXT"

# Verify tools exist
podman run --rm "$IMAGE" bash -c "
  command -v zsh
  command -v fzf
  command -v shellcheck
  python3.12 --version
"

# Rebuild (idempotency)
podman build --no-cache -f "$REPO_ROOT/images/Containerfile.extras" -t "$IMAGE" "$BUILD_CONTEXT"

# Verify again
podman run --rm "$IMAGE" bash -c "
  command -v zsh
  command -v fzf
  command -v shellcheck
  python3.12 --version
"

# Cleanup
podman rmi "$IMAGE" 2>/dev/null || true

echo "PASS: extras build and are idempotent"
