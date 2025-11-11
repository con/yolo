#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="con-bomination-claude-code"
DOCKERFILE_DIR="$SCRIPT_DIR/images"

echo "🚀 Claude Code YOLO Mode Setup"
echo "================================"
echo

# Check if image exists
if podman image exists "$IMAGE_NAME" 2>/dev/null; then
    echo "✓ Container image '$IMAGE_NAME' already exists"
else
    echo "Building container image '$IMAGE_NAME'..."
    echo "This may take a few minutes on first run..."
    echo

    TZ=$(timedatectl show --property=Timezone --value 2>/dev/null || echo "UTC")
    podman build --build-arg "TZ=$TZ" -t "$IMAGE_NAME" "$DOCKERFILE_DIR"

    echo
    echo "✓ Container image built successfully"
fi

echo
echo "================================"
echo

# Install YOLO script to ~/.local/bin
BIN_DIR="$HOME/.local/bin"
YOLO_SCRIPT="$BIN_DIR/yolo"

# Create directory if it doesn't exist
mkdir -p "$BIN_DIR"

# Check if yolo script already exists
if [ -f "$YOLO_SCRIPT" ]; then
    echo "✓ yolo script already exists at $YOLO_SCRIPT"
    echo
    read -p "Overwrite existing script? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo
        echo "Setup complete! Container image is ready."
        echo "Use existing 'yolo' command from any directory."
        exit 0
    fi
fi

# Ask user if they want to install the script
echo "Would you like to install the 'yolo' command?"
echo
echo "This will create a script at $YOLO_SCRIPT that lets you run:"
echo "  $ yolo"
echo
echo "from any directory to start Claude Code in YOLO mode (auto-approve all actions)."
echo
read -p "Install yolo command? [y/N] " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo
    echo "Setup complete! Container image is ready."
    echo "Run manually with:"
    echo "  podman run -it --rm --userns=keep-id \\"
    echo "    -v ~/.claude:/claude:Z \\"
    echo "    -v ~/.gitconfig:/tmp/.gitconfig:ro,Z \\"
    echo "    -v \"\$(pwd):/workspace:Z\" \\"
    echo "    -w /workspace \\"
    echo "    -e CLAUDE_CONFIG_DIR=/claude \\"
    echo "    -e GIT_CONFIG_GLOBAL=/tmp/.gitconfig \\"
    echo "    $IMAGE_NAME \\"
    echo "    claude --dangerously-skip-permissions"
    echo
    echo "Pass extra podman options and claude arguments like:"
    echo "  podman run ... [podman-options] $IMAGE_NAME claude [claude-args]"
    exit 0
fi

# Create yolo script
echo
echo "Installing yolo script to $YOLO_SCRIPT..."

cat > "$YOLO_SCRIPT" << 'EOF'
#!/bin/bash
# Claude Code YOLO mode - auto-approve all actions in containerized environment

# Parse arguments: everything before -- goes to podman, everything after goes to claude
PODMAN_ARGS=()
CLAUDE_ARGS=()
found_separator=false

for arg in "$@"; do
    if [ "$arg" = "--" ]; then
        found_separator=true
    elif [ "$found_separator" = true ]; then
        CLAUDE_ARGS+=("$arg")
    else
        PODMAN_ARGS+=("$arg")
    fi
done

podman run -it --rm \
    --userns=keep-id \
    -v ~/.claude:/claude:Z \
    -v ~/.gitconfig:/tmp/.gitconfig:ro,Z \
    -v "$(pwd):/workspace:Z" \
    -w /workspace \
    -e CLAUDE_CONFIG_DIR=/claude \
    -e GIT_CONFIG_GLOBAL=/tmp/.gitconfig \
    "${PODMAN_ARGS[@]}" \
    con-bomination-claude-code \
    claude --dangerously-skip-permissions "${CLAUDE_ARGS[@]}"
EOF

chmod +x "$YOLO_SCRIPT"

echo "✓ yolo script installed to $YOLO_SCRIPT"
echo

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" == *":$BIN_DIR:"* ]]; then
    echo "✓ $BIN_DIR is already in your PATH"
else
    echo "⚠️  $BIN_DIR is not in your PATH"
    echo "   Add this line to your shell config (~/.bashrc or ~/.zshrc):"
    echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo
fi

echo "================================"
echo "🎉 Setup complete!"
echo "================================"
echo
echo "To start using YOLO mode:"
echo "  1. Make sure ~/.local/bin is in your PATH (restart shell if needed)"
echo "  2. Navigate to any project directory"
echo "  3. Run: yolo"
echo
echo "Pass extra podman options before -- and claude arguments after:"
echo "  yolo -v /host:/container --env FOO=bar -- \"help with this code\""
echo "  yolo -v /data:/data --  # extra mounts only"
echo "  yolo -- \"process files\"  # claude args only"
echo
echo "The containerized Claude Code will start with full permissions"
echo "in the current directory, with credentials and git access configured."
echo
