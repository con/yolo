#!/bin/bash
# Test script with FIXED argument parsing logic

echo "=== Testing FIXED argument parsing logic ==="
echo

test_args() {
    echo "Test: $@"
    echo "---"

    PODMAN_ARGS=()
    CLAUDE_ARGS=()
    found_separator=0
    USE_GLOBAL_CLAUDE=0

    for arg in "$@"; do
        if [ "$arg" = "--global-claude" ]; then
            USE_GLOBAL_CLAUDE=1
        elif [ "$found_separator" -eq 0 ] && [ "$arg" = "--" ]; then  # FIXED: exact match
            found_separator=1
            echo "  Separator found at: '$arg'"
        elif [ "$found_separator" -eq 1 ]; then
            CLAUDE_ARGS+=("$arg")
        else
            PODMAN_ARGS+=("$arg")
        fi
    done

    if [ "$found_separator" = 0 ]; then
        CLAUDE_ARGS=("${PODMAN_ARGS[@]}")
        PODMAN_ARGS=()
    fi

    echo "  PODMAN_ARGS: ${PODMAN_ARGS[*]}"
    echo "  CLAUDE_ARGS: ${CLAUDE_ARGS[*]}"
    echo "  USE_GLOBAL_CLAUDE: $USE_GLOBAL_CLAUDE"
    echo
}

echo "TEST 1: Basic separator"
test_args -- "help me"

echo "TEST 2: FIXED - --rm should go to podman"
test_args --rm -- "help me"

echo "TEST 3: FIXED - --env should go to podman"
test_args --env FOO=bar -- "process files"

echo "TEST 4: FIXED - Multiple podman flags"
test_args -v /tmp:/tmp --network host -- "debug this"

echo "TEST 5: FIXED - With --global-claude flag"
test_args --global-claude --rm -- "help"

echo "TEST 6: No separator - all args go to claude"
test_args "just help me"

echo "TEST 7: No separator with flags - all go to claude"
test_args "help with --verbose output"
