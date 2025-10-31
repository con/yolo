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

# Detect shell
SHELL_NAME=$(basename "$SHELL")
case "$SHELL_NAME" in
    bash)
        RC_FILE="$HOME/.bashrc"
        ;;
    zsh)
        RC_FILE="$HOME/.zshrc"
        ;;
    *)
        echo "⚠️  Unsupported shell: $SHELL_NAME"
        echo "   Manually add the YOLO function to your shell config"
        exit 0
        ;;
esac

# Check if YOLO function already exists
if grep -q "^YOLO()" "$RC_FILE" 2>/dev/null; then
    echo "✓ YOLO function already exists in $RC_FILE"
    echo
    echo "You're all set! Just run 'YOLO' from any directory to start Claude Code."
    exit 0
fi

# Ask user if they want to create the alias
echo "Would you like to create the 'YOLO' command?"
echo
echo "This will add a shell function to $RC_FILE that lets you run:"
echo "  $ YOLO"
echo
echo "from any directory to start Claude Code in YOLO mode (auto-approve all actions)."
echo
read -p "Create YOLO command? [y/N] " -n 1 -r
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
    exit 0
fi

# Add YOLO function to shell config
echo
echo "Adding YOLO function to $RC_FILE..."

cat >> "$RC_FILE" << 'EOF'

# Claude Code YOLO mode - auto-approve all actions in containerized environment
YOLO() {
    podman run -it --rm \
        --userns=keep-id \
        -v ~/.claude:/claude:Z \
        -v ~/.gitconfig:/tmp/.gitconfig:ro,Z \
        -v "$(pwd):/workspace:Z" \
        -w /workspace \
        -e CLAUDE_CONFIG_DIR=/claude \
        -e GIT_CONFIG_GLOBAL=/tmp/.gitconfig \
        con-bomination-claude-code \
        claude --dangerously-skip-permissions "$@"
}
EOF

echo "✓ YOLO function added to $RC_FILE"
echo
echo "================================"
echo "🎉 Setup complete!"
echo "================================"
echo
echo "To start using YOLO mode:"
echo "  1. Reload your shell: source $RC_FILE"
echo "  2. Navigate to any project directory"
echo "  3. Run: YOLO"
echo
echo "The containerized Claude Code will start with full permissions"
echo "in the current directory, with credentials and git access configured."
echo
