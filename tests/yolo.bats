#!/usr/bin/env bats
# Tests for bin/yolo script

setup() {
    # Load the yolo script for testing
    SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
    YOLO_SCRIPT="$SCRIPT_DIR/bin/yolo"

    # Create a test directory structure
    TEST_TEMP_DIR="$(mktemp -d)"
    export TEST_PWD="$TEST_TEMP_DIR/test-project"
    mkdir -p "$TEST_PWD"
    cd "$TEST_PWD"
}

teardown() {
    # Clean up test artifacts
    if [ -n "$TEST_TEMP_DIR" ] && [ -d "$TEST_TEMP_DIR" ]; then
        rm -rf "$TEST_TEMP_DIR"
    fi
}

@test "yolo script exists and is executable" {
    [ -f "$YOLO_SCRIPT" ]
    [ -x "$YOLO_SCRIPT" ]
}

@test "yolo script has proper shebang" {
    run head -n 1 "$YOLO_SCRIPT"
    [[ "$output" = "#!/bin/bash" ]]
}

@test "yolo script uses set -e for error handling" {
    run grep "^set -e" "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script defines correct image name" {
    # The script uses con-bomination-claude-code as the image name
    run grep "con-bomination-claude-code" "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script supports --anonymized-paths flag" {
    # Check that the script recognizes this flag
    run grep "USE_ANONYMIZED_PATHS" "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
    run grep "\-\-anonymized-paths" "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script supports --entrypoint flag" {
    # Check that the script recognizes this flag
    run grep "ENTRYPOINT=" "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
    run grep "\-\-entrypoint" "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script supports --worktree flag" {
    # Check that the script recognizes this flag
    run grep "WORKTREE_MODE" "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
    run grep "\-\-worktree=" "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script validates worktree mode values" {
    # Extract the validation regex from the script
    run grep 'ask|bind|skip|error' "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script supports -- separator for arguments" {
    # Check that the script handles -- separator
    run grep 'found_separator' "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script creates claude home directory if missing" {
    # Check that the script creates .claude directory
    run grep 'mkdir -p.*CLAUDE_HOME_DIR' "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script detects git worktrees" {
    # Check that the script has worktree detection logic
    run grep 'is_worktree' "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
    run grep 'gitdir_path' "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script generates container names based on PWD and PID" {
    # Check that container name includes PWD and PID
    run grep 'PWD-\$\$' "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script strips leading underscores from container names" {
    # Check for sed command that strips leading underscores
    run grep 's,\^_\*,,' "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script uses --log-driver=none for podman" {
    # Check that logging is disabled
    run grep "\-\-log-driver=none" "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script uses --userns=keep-id for podman" {
    # Check for proper user namespace handling
    run grep "\-\-userns=keep-id" "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script mounts .claude directory" {
    # Check that .claude directory is mounted
    run grep 'CLAUDE_MOUNT' "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script mounts .gitconfig as read-only" {
    # Check for gitconfig mount
    run grep '\.gitconfig.*:ro' "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script mounts current working directory" {
    # Check for workspace mount
    run grep 'WORKSPACE_MOUNT' "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script sets CLAUDE_CONFIG_DIR environment variable" {
    # Check for CLAUDE_CONFIG_DIR
    run grep 'CLAUDE_CONFIG_DIR' "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script sets GIT_CONFIG_GLOBAL environment variable" {
    # Check for GIT_CONFIG_GLOBAL
    run grep 'GIT_CONFIG_GLOBAL' "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script uses --dangerously-skip-permissions by default" {
    # Check for the dangerous skip permissions flag
    run grep "\-\-dangerously-skip-permissions" "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script sanitizes container names" {
    # Check for name sanitization logic
    run grep 's,\[^a-zA-Z0-9_\.\-\]' "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script removes HOME prefix from container names" {
    # Check for HOME removal in name generation
    run grep 's,\^\$HOME/' "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script handles .git as symlink for worktree detection" {
    # Check for symlink detection
    run grep '\[ -L "\$dot_git" \]' "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script handles .git as file for worktree detection" {
    # Check for file detection
    run grep '\[ -f "\$dot_git" \]' "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "yolo script parses gitdir from .git file" {
    # Check for gitdir parsing
    run grep 'gitdir:' "$YOLO_SCRIPT"
    [ "$status" -eq 0 ]
}
