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

@test "--tag: default image reference is :latest" {
    run_yolo
    assert_success
    podman_args_contain "con-bomination-claude-code:latest"
}

@test "--tag=TAG: image reference uses the given tag" {
    run_yolo --tag=test
    assert_success
    podman_args_contain "con-bomination-claude-code:test"
    refute_podman_arg "con-bomination-claude-code:latest"
}

@test "--tag TAG: space-separated form works" {
    run_yolo --tag test
    assert_success
    podman_args_contain "con-bomination-claude-code:test"
}

@test "--tag: invalid tag exits with error" {
    run_yolo --tag="bad:tag"
    assert_failure
    assert_output --partial "Invalid image tag"
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

@test "config: YOLO_IMAGE_TAG selects the image tag" {
    write_user_config << 'EOF'
YOLO_IMAGE_TAG="from-config"
EOF
    run_yolo
    assert_success
    podman_args_contain "con-bomination-claude-code:from-config"
}

@test "config: project YOLO_IMAGE_TAG overrides user-wide one" {
    write_user_config << 'EOF'
YOLO_IMAGE_TAG="from-user"
EOF
    write_project_config << 'EOF'
YOLO_IMAGE_TAG="from-project"
EOF
    run_yolo
    assert_success
    podman_args_contain "con-bomination-claude-code:from-project"
    refute_podman_arg "con-bomination-claude-code:from-user"
}

@test "config: --tag overrides YOLO_IMAGE_TAG from config" {
    write_project_config << 'EOF'
YOLO_IMAGE_TAG="from-config"
EOF
    run_yolo --tag=from-cli
    assert_success
    podman_args_contain "con-bomination-claude-code:from-cli"
    refute_podman_arg "con-bomination-claude-code:from-config"
}

@test "config: --no-config ignores YOLO_IMAGE_TAG from config files" {
    write_project_config << 'EOF'
YOLO_IMAGE_TAG="from-config"
EOF
    run_yolo --no-config
    assert_success
    podman_args_contain "con-bomination-claude-code:latest"
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

# ── setup-yolo.sh build arguments (end-to-end with mock podman) ───

@test "setup: --extras=cuda is accepted but passes no build arg" {
    run_setup --build=yes --extras=cuda
    assert_success
    refute_podman_arg "EXTRA_CUDA=1"
}

@test "setup: --extras=cuda prints the no-op note" {
    run_setup --build=yes --extras=cuda
    assert_success
    assert_output --partial "the cuda extra installs nothing"
    assert_output --partial "yolo --nvidia"
}

@test "setup: --cuda-version is accepted but passes no build arg" {
    run_setup --build=yes --cuda-version=12-8
    assert_success
    assert_output --partial "the cuda extra installs nothing"
    refute_podman_arg "CUDA_VERSION="
}

@test "setup: --cuda-version=13.0 (dotted) is no longer rejected" {
    run_setup --build=yes --cuda-version=13.0
    assert_success
}

@test "setup: --extras=all excludes cuda and prints no note" {
    run_setup --build=yes --extras=all
    assert_success
    refute_output --partial "installs nothing"
    refute_podman_arg "EXTRA_CUDA=1"
    podman_args_contain "EXTRA_PLAYWRIGHT=1"
    podman_args_contain "EXTRA_APPTAINER=1"
}

@test "setup: --extras=cuda,jj still passes the real extra" {
    run_setup --build=yes --extras=cuda,jj
    assert_success
    podman_args_contain "EXTRA_JJ=1"
    refute_podman_arg "EXTRA_CUDA=1"
}

@test "setup: --base-image passes BASE_IMAGE build arg" {
    run_setup --build=yes --base-image=node:22-trixie
    assert_success
    podman_args_contain "BASE_IMAGE=node:22-trixie"
}

@test "setup: --base-image is omitted when not given" {
    run_setup --build=yes
    assert_success
    refute_podman_arg "BASE_IMAGE="
}
