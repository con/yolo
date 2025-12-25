#!/usr/bin/env bats
# Tests for setup-yolo.sh script

setup() {
    # Load the setup script for testing
    SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
    SETUP_SCRIPT="$SCRIPT_DIR/setup-yolo.sh"

    # Create a temporary directory for test artifacts
    TEST_TEMP_DIR="$(mktemp -d)"
    export TEST_HOME="$TEST_TEMP_DIR/home"
    mkdir -p "$TEST_HOME/.local/bin"
}

teardown() {
    # Clean up test artifacts
    if [ -n "$TEST_TEMP_DIR" ] && [ -d "$TEST_TEMP_DIR" ]; then
        rm -rf "$TEST_TEMP_DIR"
    fi
}

@test "setup script exists and is executable" {
    [ -f "$SETUP_SCRIPT" ]
    [ -x "$SETUP_SCRIPT" ]
}

@test "setup script shows help with --help flag" {
    run bash "$SETUP_SCRIPT" --help
    [ "$status" -eq 0 ]
    [[ "$output" =~ "Usage: setup-yolo.sh" ]]
    [[ "$output" =~ "OPTIONS:" ]]
}

@test "setup script shows help with -h flag" {
    run bash "$SETUP_SCRIPT" -h
    [ "$status" -eq 0 ]
    [[ "$output" =~ "Usage: setup-yolo.sh" ]]
}

@test "setup script rejects invalid --build option" {
    run bash "$SETUP_SCRIPT" --build=invalid
    [ "$status" -eq 1 ]
    [[ "$output" =~ "Error: --build must be one of: auto, yes, no" ]]
}

@test "setup script rejects invalid --install option" {
    run bash "$SETUP_SCRIPT" --install=invalid
    [ "$status" -eq 1 ]
    [[ "$output" =~ "Error: --install must be one of: auto, yes, no" ]]
}

@test "setup script rejects unknown options" {
    run bash "$SETUP_SCRIPT" --unknown-option
    [ "$status" -eq 1 ]
    [[ "$output" =~ "Unknown option:" ]]
}

@test "setup script accepts --build=auto" {
    # This test will skip build if image doesn't exist unless we mock podman
    skip "Requires podman mocking or actual image"
}

@test "setup script accepts --build=yes" {
    skip "Requires podman mocking or actual image"
}

@test "setup script accepts --build=no" {
    skip "Requires podman mocking or actual image"
}

@test "setup script accepts --install=auto" {
    skip "Requires podman mocking or actual image"
}

@test "setup script accepts --install=yes" {
    skip "Requires podman mocking or actual image"
}

@test "setup script accepts --install=no" {
    skip "Requires podman mocking or actual image"
}

@test "setup script defines correct image name" {
    # Extract IMAGE_NAME from script
    image_name=$(grep '^IMAGE_NAME=' "$SETUP_SCRIPT" | cut -d'"' -f2)
    [ "$image_name" = "con-bomination-claude-code" ]
}

@test "setup script defines correct dockerfile directory" {
    # Check that DOCKERFILE_DIR is set to images subdirectory
    run grep 'DOCKERFILE_DIR=.*images' "$SETUP_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "setup script has proper shebang" {
    run head -n 1 "$SETUP_SCRIPT"
    [[ "$output" = "#!/bin/bash" ]]
}

@test "setup script uses set -e for error handling" {
    run grep "^set -e" "$SETUP_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "setup script help includes examples" {
    run bash "$SETUP_SCRIPT" --help
    [ "$status" -eq 0 ]
    [[ "$output" =~ "EXAMPLES:" ]]
}

@test "setup script validates build mode values" {
    # Valid values should be documented in help
    run bash "$SETUP_SCRIPT" --help
    [[ "$output" =~ "auto - build only if image doesn't exist" ]]
    [[ "$output" =~ "yes  - always rebuild the image" ]]
    [[ "$output" =~ "no   - skip building" ]]
}

@test "setup script validates install mode values" {
    # Valid values should be documented in help
    run bash "$SETUP_SCRIPT" --help
    [[ "$output" =~ "auto - install if missing or prompt if exists and differs" ]]
    [[ "$output" =~ "yes  - always install/overwrite without prompting" ]]
    [[ "$output" =~ "no   - skip installation" ]]
}
