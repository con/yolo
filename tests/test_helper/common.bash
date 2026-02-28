# Common test helpers for yolo BATS tests

YOLO_BIN="$(cd "$BATS_TEST_DIRNAME/.." && pwd)/bin/yolo"

# ── setup / teardown ──────────────────────────────────────────────

setup() {
    # Create isolated directory structure
    export TEST_HOME="$BATS_TEST_TMPDIR/home"
    export TEST_REPO="$BATS_TEST_TMPDIR/repo"
    export TEST_BIN="$BATS_TEST_TMPDIR/bin"

    mkdir -p "$TEST_HOME/.claude" "$TEST_HOME/.config/yolo"
    mkdir -p "$TEST_REPO/.git/yolo"
    mkdir -p "$TEST_BIN"

    # Minimal .gitconfig so yolo doesn't fail on the -v .gitconfig mount
    printf '[user]\n    name = test\n' > "$TEST_HOME/.gitconfig"

    # Create mock podman that captures args.
    # Use unquoted heredoc so $BATS_TEST_TMPDIR is expanded at write time.
    cat > "$TEST_BIN/podman" << MOCK
#!/bin/bash
for arg in "\$@"; do
    printf '%s\\n' "\$arg"
done > "$BATS_TEST_TMPDIR/podman_args"
exit 0
MOCK
    chmod +x "$TEST_BIN/podman"
}

teardown() {
    # bats handles BATS_TEST_TMPDIR cleanup
    :
}

# ── helpers ───────────────────────────────────────────────────────

# Source function definitions from bin/yolo without executing the main body.
# Extracts everything above the argument-parsing section, strips the shebang
# and `set -e`, then evals it.  This is more robust than per-function sed
# extraction which depends on matching closing braces at column 0.
load_yolo_functions() {
    eval "$(sed -n '2,/^# Parse arguments/{
        /^set -e$/d
        /^# Parse arguments/d
        p
    }' "$YOLO_BIN")"
}

# Run yolo with mocked environment from the test repo directory.
# Each @test runs in its own subshell, so exports don't leak.
run_yolo() {
    cd "$TEST_REPO"
    export HOME="$TEST_HOME"
    export PATH="$TEST_BIN:$PATH"
    export XDG_CONFIG_HOME="$TEST_HOME/.config"
    run bash "$YOLO_BIN" "$@"
}

# Read captured podman args (one per line)
get_podman_args() {
    cat "$BATS_TEST_TMPDIR/podman_args" 2>/dev/null
}

# Check if a string appears in podman args
podman_args_contain() {
    get_podman_args | grep -qF -- "$1"
}

# Assert that a string does NOT appear in podman args.
# Produces diagnostic output on failure.
refute_podman_arg() {
    run podman_args_contain "$1"
    if [ "$status" -eq 0 ]; then
        echo "Expected podman args NOT to contain: $1" >&2
        echo "Actual podman args:" >&2
        get_podman_args >&2
        return 1
    fi
}

# Write user-wide config (pipe content via heredoc)
write_user_config() {
    mkdir -p "$TEST_HOME/.config/yolo"
    cat > "$TEST_HOME/.config/yolo/config"
}

# Write project config (pipe content via heredoc)
write_project_config() {
    mkdir -p "$TEST_REPO/.git/yolo"
    cat > "$TEST_REPO/.git/yolo/config"
}
