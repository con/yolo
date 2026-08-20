#!/usr/bin/env bats

load 'test_helper/bats-support/load'
load 'test_helper/bats-assert/load'

SETUP_SCRIPT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)/setup-yolo.sh"
DOCKERFILE_DIR="$(cd "$BATS_TEST_DIRNAME/.." && pwd)/images"

setup() {
    export TEST_BIN="$BATS_TEST_TMPDIR/bin"
    mkdir -p "$TEST_BIN"

    # Mock podman: record all args to a file and succeed.
    cat > "$TEST_BIN/podman" << MOCK
#!/bin/bash
printf '%s\n' "\$@" >> "$BATS_TEST_TMPDIR/podman_args"
exit 0
MOCK
    chmod +x "$TEST_BIN/podman"

    # Mock timedatectl so TZ detection works offline.
    cat > "$TEST_BIN/timedatectl" << 'MOCK'
#!/bin/bash
echo "UTC"
MOCK
    chmod +x "$TEST_BIN/timedatectl"
}

teardown() {
    :
}

get_podman_args() {
    cat "$BATS_TEST_TMPDIR/podman_args" 2>/dev/null
}

run_setup() {
    PATH="$TEST_BIN:$PATH" \
    bash "$SETUP_SCRIPT" "$@"
}

# ── YOLO_BUILD_CMD build-arg ──────────────────────────────────────

@test "setup-yolo: YOLO_BUILD_CMD build-arg is passed to podman build" {
    run run_setup --build=yes --install=no
    assert_success
    run grep "YOLO_BUILD_CMD=" "$BATS_TEST_TMPDIR/podman_args"
    assert_success
}

@test "setup-yolo: YOLO_BUILD_CMD includes the script name" {
    run run_setup --build=yes --install=no
    assert_success
    run grep "YOLO_BUILD_CMD=setup-yolo.sh" "$BATS_TEST_TMPDIR/podman_args"
    assert_success
}

@test "setup-yolo: YOLO_BUILD_CMD records extra CLI flags" {
    run run_setup --build=yes --install=no --packages=vim
    assert_success
    run grep "YOLO_BUILD_CMD=setup-yolo.sh.*--packages=vim" "$BATS_TEST_TMPDIR/podman_args"
    assert_success
}
