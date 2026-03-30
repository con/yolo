#!/bin/bash
# Test script to demonstrate argument parsing behavior

echo "=== Testing argument parsing logic ==="
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
        elif [ "$found_separator" -eq 0 ] && [ "${arg:0:2}" = "--" ]; then
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

echo "TEST 1: Expected behavior - should work"
test_args -- "help me"

echo "TEST 2: Bug demonstration - --rm should go to podman, not be separator"
test_args --rm -- "help me"

echo "TEST 3: Another example with --env"
test_args --env FOO=bar -- "process files"

echo "TEST 4: Multiple podman flags"
test_args -v /tmp:/tmp --network host -- "debug this"

echo "TEST 5: With --global-claude flag"
test_args --global-claude --rm -- "help"
