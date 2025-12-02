#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="con-bomination-claude-code"
DOCKERFILE_DIR="$SCRIPT_DIR/images"

# Default options
BUILD_MODE="auto"
INSTALL_MODE="auto"

show_help() {
    cat << EOF
Usage: setup-yolo.sh [OPTIONS]

Setup script for Claude Code YOLO Mode containerized environment.

OPTIONS:
    -h, --help              Show this help message
    --build=MODE            Control image building (default: auto)
                            auto - build only if image doesn't exist
                            yes  - always rebuild the image
                            no   - skip building (error if image missing)
    --install=MODE          Control yolo script installation (default: auto)
                            auto - install if missing or prompt if exists and differs
                            yes  - always install/overwrite without prompting
                            no   - skip installation

EXAMPLES:
    # Interactive setup (default)
    ./setup-yolo.sh

    # Rebuild image after Dockerfile changes
    ./setup-yolo.sh --build=yes

    # Rebuild and force install
    ./setup-yolo.sh --build=yes --install=yes

    # Only build image if needed, don't install script
    ./setup-yolo.sh --install=no

    # Build if needed, auto-install intelligently
    ./setup-yolo.sh --build=auto --install=auto

EOF
    exit 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            ;;
        --build=*)
            BUILD_MODE="${1#*=}"
            if [[ ! "$BUILD_MODE" =~ ^(auto|yes|no)$ ]]; then
                echo "Error: --build must be one of: auto, yes, no"
                exit 1
            fi
            shift
            ;;
        --install=*)
            INSTALL_MODE="${1#*=}"
            if [[ ! "$INSTALL_MODE" =~ ^(auto|yes|no)$ ]]; then
                echo "Error: --install must be one of: auto, yes, no"
                exit 1
            fi
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run with --help for usage information"
            exit 1
            ;;
    esac
done

echo "🚀 Claude Code YOLO Mode Setup"
echo "================================"
echo

# Handle image building based on BUILD_MODE
IMAGE_EXISTS=false
if podman image exists "$IMAGE_NAME" 2>/dev/null; then
    IMAGE_EXISTS=true
fi

if [ "$BUILD_MODE" = "no" ]; then
    if [ "$IMAGE_EXISTS" = false ]; then
        echo "Error: Image '$IMAGE_NAME' does not exist and --build=no was specified"
        exit 1
    fi
    echo "✓ Skipping build (--build=no specified)"
elif [ "$BUILD_MODE" = "yes" ] || [ "$IMAGE_EXISTS" = false ]; then
    if [ "$BUILD_MODE" = "yes" ]; then
        echo "Rebuilding container image '$IMAGE_NAME'..."
    else
        echo "Building container image '$IMAGE_NAME'..."
    fi
    echo "This may take a few minutes..."
    echo

    TZ=$(timedatectl show --property=Timezone --value 2>/dev/null || echo "UTC")
    podman build --build-arg "TZ=$TZ" -t "$IMAGE_NAME" "$DOCKERFILE_DIR"

    echo
    echo "✓ Container image built successfully"
else
    # BUILD_MODE=auto and image exists
    echo "✓ Container image '$IMAGE_NAME' already exists"
fi

echo
echo "================================"
echo

# Install YOLO script to ~/.local/bin
BIN_DIR="$HOME/.local/bin"
YOLO_SCRIPT="$BIN_DIR/yolo"
SOURCE_SCRIPT="$SCRIPT_DIR/bin/yolo"

# Create directory if it doesn't exist
mkdir -p "$BIN_DIR"

# Determine if we should install based on INSTALL_MODE
SHOULD_INSTALL=false
SCRIPT_EXISTS=false

if [ -f "$YOLO_SCRIPT" ]; then
    SCRIPT_EXISTS=true
fi

if [ "$INSTALL_MODE" = "no" ]; then
    echo "Skipping yolo script installation (--install=no specified)"
elif [ "$INSTALL_MODE" = "yes" ]; then
    # Always install
    SHOULD_INSTALL=true
    if [ "$SCRIPT_EXISTS" = true ]; then
        echo "Overwriting existing yolo script (--install=yes specified)"
    else
        echo "Installing yolo script (--install=yes specified)"
    fi
elif [ "$INSTALL_MODE" = "auto" ]; then
    if [ "$SCRIPT_EXISTS" = false ]; then
        # Script doesn't exist, ask if user wants to install
        echo "Would you like to install the 'yolo' command?"
        echo
        echo "This will create a script at $YOLO_SCRIPT that lets you run:"
        echo "  $ yolo"
        echo
        echo "from any directory to start Claude Code in YOLO mode (auto-approve all actions)."
        echo
        read -p "Install yolo command? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            SHOULD_INSTALL=true
        fi
    else
        # Script exists, check if it differs
        if ! cmp -s "$SOURCE_SCRIPT" "$YOLO_SCRIPT"; then
            echo "✓ yolo script already exists at $YOLO_SCRIPT"
            echo "  (but differs from source)"
            echo
            read -p "Overwrite existing script? [y/N] " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                SHOULD_INSTALL=true
            fi
        else
            echo "✓ yolo script already exists and is up to date at $YOLO_SCRIPT"
        fi
    fi
fi

if [ "$SHOULD_INSTALL" = false ]; then
    echo
    echo "Setup complete! Container image is ready."
    echo "Run manually with preserved host paths (default):"
    echo "  podman run -it --rm --userns=keep-id \\"
    echo "    -v ~/.claude:~/.claude:Z \\"
    echo "    -v ~/.gitconfig:/tmp/.gitconfig:ro,Z \\"
    echo "    -v \"\$(pwd):\$(pwd):Z\" \\"
    echo "    -w \"\$(pwd)\" \\"
    echo "    -e CLAUDE_CONFIG_DIR=~/.claude \\"
    echo "    -e GIT_CONFIG_GLOBAL=/tmp/.gitconfig \\"
    echo "    $IMAGE_NAME \\"
    echo "    claude --dangerously-skip-permissions"
    echo
    echo "Or with anonymized paths (/claude, /workspace):"
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

# Install yolo script
if [ "$SHOULD_INSTALL" = true ]; then
    echo
    echo "Installing yolo script to $YOLO_SCRIPT..."

    cp "$SOURCE_SCRIPT" "$YOLO_SCRIPT"
    chmod +x "$YOLO_SCRIPT"

    echo "✓ yolo script installed to $YOLO_SCRIPT"
    echo
fi

# Check if ~/.local/bin is in PATH (only if we installed)
if [ "$SHOULD_INSTALL" = true ]; then
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
    echo "By default, yolo preserves original host paths for session compatibility."
    echo "Use --anonymized-paths flag for anonymized paths (/claude, /workspace):"
    echo "  yolo --anonymized-paths"
    echo
    echo "Pass extra podman options before -- and claude arguments after:"
    echo "  yolo -v /host:/container --env FOO=bar -- \"help with this code\""
    echo "  yolo -v /data:/data --  # extra mounts only"
    echo "  yolo -- \"process files\"  # claude args only"
    echo
    echo "The containerized Claude Code will start with full permissions"
    echo "in the current directory, with credentials and git access configured."
    echo
fi
