#!/usr/bin/env bats

load 'test_helper/bats-support/load'
load 'test_helper/bats-assert/load'
load 'test_helper/common'

# ── expand_volume (function-level) ────────────────────────────────

@test "expand_volume: shorthand ~/path expands to 1-to-1 mount with :Z" {
    load_yolo_functions
    export HOME="$TEST_HOME"
    run expand_volume "~/projects"
    assert_output "$TEST_HOME/projects:$TEST_HOME/projects:Z"
}

@test "expand_volume: shorthand with options ~/data::ro" {
    load_yolo_functions
    export HOME="$TEST_HOME"
    run expand_volume "~/data::ro"
    assert_output "$TEST_HOME/data:$TEST_HOME/data:ro"
}

@test "expand_volume: full form host:container:options passed through" {
    load_yolo_functions
    run expand_volume "~/data:/data:Z"
    assert_output "~/data:/data:Z"
}

@test "expand_volume: partial form host:container gets :Z appended" {
    load_yolo_functions
    run expand_volume "/host:/container"
    assert_output "/host:/container:Z"
}

# ── dedup_mount_specs (function-level) ────────────────────────────

@test "dedup_mount_specs: keeps last occurrence per host path" {
    load_yolo_functions
    dedup_mount_specs "/a:/a:Z" "/b:/b:Z" "/a:/a:z"
    [ "${#DEDUPED_MOUNT_SPECS[@]}" -eq 2 ]
    [ "${DEDUPED_MOUNT_SPECS[0]}" = "/b:/b:Z" ]
    [ "${DEDUPED_MOUNT_SPECS[1]}" = "/a:/a:z" ]
}

@test "dedup_mount_specs: no duplicates preserves order and count" {
    load_yolo_functions
    dedup_mount_specs "/a:/a:z" "/b:/b:z" "/c:/c:z"
    [ "${#DEDUPED_MOUNT_SPECS[@]}" -eq 3 ]
    [ "${DEDUPED_MOUNT_SPECS[0]}" = "/a:/a:z" ]
    [ "${DEDUPED_MOUNT_SPECS[2]}" = "/c:/c:z" ]
}

@test "dedup_mount_specs: empty input gives empty output" {
    load_yolo_functions
    dedup_mount_specs
    [ "${#DEDUPED_MOUNT_SPECS[@]}" -eq 0 ]
}

# ── CLI flags (end-to-end with mock podman) ───────────────────────

@test "--help: prints usage and exits 0" {
    run_yolo --help
    assert_success
    assert_output --partial "Usage: yolo"
}

@test "--no-config: podman runs without config-derived volumes" {
    write_user_config << 'EOF'
YOLO_PODMAN_VOLUMES=("~/skills")
EOF
    write_project_config << 'EOF'
YOLO_PODMAN_VOLUMES=("~/data")
EOF
    run_yolo --no-config
    assert_success
    refute_podman_arg "/skills"
    refute_podman_arg "/data"
}

@test "--anonymized-paths: workspace mount uses /workspace" {
    run_yolo --anonymized-paths
    assert_success
    podman_args_contain "/workspace:z"
}

@test "--nvidia: podman args contain --device nvidia.com/gpu=all" {
    run_yolo --nvidia
    assert_success
    podman_args_contain "--device"
    podman_args_contain "nvidia.com/gpu=all"
}

@test "--entrypoint=bash: container command starts with bash, no --dangerously-skip-permissions" {
    run_yolo --entrypoint=bash
    assert_success
    podman_args_contain "bash"
    refute_podman_arg "--dangerously-skip-permissions"
}

@test "--worktree=invalid: exits with error" {
    run_yolo --worktree=invalid
    assert_failure
    assert_output --partial "Invalid --worktree value"
}

# ── Separator (--) and argument routing ───────────────────────────

@test "separator: args after -- become claude container args" {
    run_yolo -- "--resume" "prompt text"
    assert_success
    podman_args_contain "--resume"
    podman_args_contain "prompt text"
}

@test "no separator: all positional args go to claude, not podman" {
    run_yolo "some prompt"
    assert_success
    podman_args_contain "some prompt"
    podman_args_contain "--dangerously-skip-permissions"
}

@test "default entrypoint: claude --dangerously-skip-permissions is used" {
    run_yolo
    assert_success
    podman_args_contain "claude"
    podman_args_contain "--dangerously-skip-permissions"
}

# ── Config loading & merging (end-to-end) ─────────────────────────

@test "config: user config volumes appear in podman args" {
    write_user_config << 'EOF'
YOLO_PODMAN_VOLUMES=("~/skills")
EOF
    run_yolo
    assert_success
    podman_args_contain "$TEST_HOME/skills:$TEST_HOME/skills:Z"
}

@test "config: project config volumes appear in podman args" {
    write_project_config << 'EOF'
YOLO_PODMAN_VOLUMES=("~/data")
EOF
    run_yolo
    assert_success
    podman_args_contain "$TEST_HOME/data:$TEST_HOME/data:Z"
}

@test "config: arrays merge — user + project volumes both present" {
    write_user_config << 'EOF'
YOLO_PODMAN_VOLUMES=("~/skills")
EOF
    write_project_config << 'EOF'
YOLO_PODMAN_VOLUMES=("~/data")
EOF
    run_yolo
    assert_success
    podman_args_contain "$TEST_HOME/skills:$TEST_HOME/skills:Z"
    podman_args_contain "$TEST_HOME/data:$TEST_HOME/data:Z"
}

@test "config: duplicate volumes across user + project are deduplicated" {
    write_user_config << 'EOF'
YOLO_PODMAN_VOLUMES=("~/data")
EOF
    write_project_config << 'EOF'
YOLO_PODMAN_VOLUMES=("~/data")
EOF
    run_yolo
    assert_success
    local expanded="$TEST_HOME/data:$TEST_HOME/data:Z"
    local count
    count=$(get_podman_args | grep -cFx -- "$expanded")
    [ "$count" -eq 1 ]
}

@test "config: duplicate volumes within a single config are deduplicated" {
    write_project_config << 'EOF'
YOLO_PODMAN_VOLUMES=("~/data" "~/data")
EOF
    run_yolo
    assert_success
    local expanded="$TEST_HOME/data:$TEST_HOME/data:Z"
    local count
    count=$(get_podman_args | grep -cFx -- "$expanded")
    [ "$count" -eq 1 ]
}

@test "config: volume matching CWD is dropped (workspace mount wins)" {
    # Use unquoted heredoc so $TEST_REPO interpolates
    write_user_config <<EOF
YOLO_PODMAN_VOLUMES=("$TEST_REPO")
EOF
    run_yolo
    assert_success
    # Workspace mount (lowercase :z) must still be present
    podman_args_contain "$TEST_REPO:$TEST_REPO:z"
    # Config-derived duplicate (uppercase :Z) must NOT be added
    refute_podman_arg "$TEST_REPO:$TEST_REPO:Z"
    # Exactly one -v entry for this host path
    local count
    count=$(get_podman_args | grep -cE "^${TEST_REPO}:${TEST_REPO}:[zZ]\$")
    [ "$count" -eq 1 ]
}

@test "config: volume matching ~/.claude is dropped" {
    write_user_config << 'EOF'
YOLO_PODMAN_VOLUMES=("~/.claude")
EOF
    run_yolo
    assert_success
    # Default claude mount (lowercase :z) is present
    podman_args_contain "$TEST_HOME/.claude:$TEST_HOME/.claude:z"
    # Config-derived duplicate (uppercase :Z) is not
    refute_podman_arg "$TEST_HOME/.claude:$TEST_HOME/.claude:Z"
}

@test "dedup: CLI -v overrides config for the same host path" {
    write_user_config << 'EOF'
YOLO_PODMAN_VOLUMES=("~/data")
EOF
    run_yolo -v "$TEST_HOME/data:/elsewhere:ro" --
    assert_success
    podman_args_contain "$TEST_HOME/data:/elsewhere:ro"
    refute_podman_arg "$TEST_HOME/data:$TEST_HOME/data:Z"
}

@test "dedup: CLI -v on workspace path overrides default workspace mount" {
    run_yolo -v "$TEST_REPO:/elsewhere:ro" --
    assert_success
    podman_args_contain "$TEST_REPO:/elsewhere:ro"
    refute_podman_arg "$TEST_REPO:$TEST_REPO:z"
}

@test "dedup: config volume matching worktree original repo is dropped" {
    # Build a fake git worktree: $TEST_REPO/.git is a file whose gitdir
    # points to an "original" repo elsewhere under BATS_TEST_TMPDIR.
    local tmpbase fake_orig
    tmpbase=$(realpath "$BATS_TEST_TMPDIR")
    fake_orig="$tmpbase/orig-repo"
    mkdir -p "$fake_orig/.git/worktrees/test-wt"
    rm -rf "$TEST_REPO/.git"
    echo "gitdir: $fake_orig/.git/worktrees/test-wt" > "$TEST_REPO/.git"

    write_user_config <<EOF
YOLO_PODMAN_VOLUMES=("$fake_orig")
EOF
    run_yolo --worktree=bind
    assert_success
    # Worktree mount (lowercase :z) is present, config :Z is dropped
    podman_args_contain "$fake_orig:$fake_orig:z"
    refute_podman_arg "$fake_orig:$fake_orig:Z"
    # Exactly one -v entry for this host path
    local count
    count=$(get_podman_args | grep -cE "^${fake_orig}:${fake_orig}:[zZ]\$")
    [ "$count" -eq 1 ]
}

@test "config: scalar override — project USE_NVIDIA=0 overrides user USE_NVIDIA=1" {
    write_user_config << 'EOF'
USE_NVIDIA=1
EOF
    write_project_config << 'EOF'
USE_NVIDIA=0
EOF
    run_yolo
    assert_success
    refute_podman_arg "nvidia.com/gpu=all"
}

@test "config: --no-config suppresses both user and project configs" {
    write_user_config << 'EOF'
YOLO_PODMAN_VOLUMES=("~/skills")
EOF
    write_project_config << 'EOF'
YOLO_PODMAN_VOLUMES=("~/data")
EOF
    run_yolo --no-config
    assert_success
    refute_podman_arg "/skills"
    refute_podman_arg "/data"
}

@test "config: XDG_CONFIG_HOME override loads user config from custom path" {
    local custom_xdg="$BATS_TEST_TMPDIR/custom-config"
    mkdir -p "$custom_xdg/yolo"
    cat > "$custom_xdg/yolo/config" << 'EOF'
YOLO_PODMAN_VOLUMES=("~/from-custom-xdg")
EOF
    cd "$TEST_REPO"
    export HOME="$TEST_HOME"
    export PATH="$TEST_BIN:$PATH"
    export XDG_CONFIG_HOME="$custom_xdg"
    run bash "$YOLO_BIN"
    assert_success
    podman_args_contain "$TEST_HOME/from-custom-xdg:$TEST_HOME/from-custom-xdg:Z"
}

@test "config: YOLO_PODMAN_OPTIONS appear in podman args" {
    write_user_config << 'EOF'
YOLO_PODMAN_OPTIONS=("--network=host")
EOF
    run_yolo
    assert_success
    podman_args_contain "--network=host"
}

@test "config: YOLO_CLAUDE_ARGS appear in container command" {
    write_user_config << 'EOF'
YOLO_CLAUDE_ARGS=("--verbose")
EOF
    run_yolo
    assert_success
    podman_args_contain "--verbose"
}

# ── Environment variables & container setup ───────────────────────

@test "env: CLAUDE_CONFIG_DIR is set in container" {
    run_yolo
    assert_success
    podman_args_contain "CLAUDE_CONFIG_DIR=$TEST_HOME/.claude"
}

@test "env: GIT_CONFIG_GLOBAL is set to /tmp/.gitconfig" {
    run_yolo
    assert_success
    podman_args_contain "GIT_CONFIG_GLOBAL=/tmp/.gitconfig"
}

@test "env: CLAUDE_CODE_OAUTH_TOKEN is passed through" {
    run_yolo
    assert_success
    podman_args_contain "CLAUDE_CODE_OAUTH_TOKEN"
}

@test "container: --name flag is present" {
    run_yolo
    assert_success
    local args
    args=$(get_podman_args)
    run grep "^--name=" <<< "$args"
    assert_success
}

# ── Config template ───────────────────────────────────────────────

@test "--install-config: output contains user-wide config path reference" {
    run_yolo --install-config
    assert_success
    assert_output --partial "yolo/config"
}
