https://github.com/con/yolo/issues/46

# Login not persistent: $HOME mismatch between host and container

## Problem

  The README states that credentials are stored in `~/.claude` and login only needs to happen once. However, login is not persistent across container
  restarts because the host `$HOME` path differs from the container user `$HOME`.

  ## Details

  The container launch uses:
  -v "$HOME/.claude:$HOME/.claude:Z"

  `$HOME` is expanded **on the host** (e.g., `/home/meng`), so credentials are mounted at `/home/meng/.claude` inside the container.

  However, inside the container the user is `node` with `HOME=/home/node`. Claude Code looks for credentials at `$HOME/.claude` → `/home/node/.claude`,
  which is empty. So every session requires a fresh `/login`.

  ## Workaround

  ```bash
  ln -s /home/meng/.claude /home/node/.claude

  (Replace /home/meng with your actual host $HOME.)

  Suggested fix

  Either:
  1. Mount to the container user home: -v "$HOME/.claude:/home/node/.claude:Z"
  2. Set HOME inside the container to match the host: --env HOME=$HOME

  Option 2 is probably simplest.

  Environment

  - Host user: meng ($HOME=/home/meng)
  - Container user: node ($HOME=/home/node)
  - Using --userns=keep-id

## Comments

### yarikoptic (2026-03-03T00:04:18Z)

are you running on linux and is above your analysis or of claude as to state `- Container user: node ($HOME=/home/node)`?

1. for credentials I just blamed

- https://github.com/anthropics/claude-code/issues/1757

for which my workaround was just to point to the file with the key via

```
CLAUDE_CODE_OAUTH_TOKEN=$(cat ~/...secretlocation) yolo ...
```

2.
The option 2, if situation is actually as you describe, could also likely address

- https://github.com/con/yolo/issues/36

which kept annoying me by creating all those `.cache/` and `.npm/` folders around!    But here is what I see in my `yolo` session:

```
! pwd
  ⎿  /home/yoh/.tmp

! echo $HOME
  ⎿  /home/yoh/.tmp

! echo $USER
  ⎿  (No output)

! whoami
  ⎿  yoh

! ls /home/
  ⎿  node
     yoh

! ls /home/node/
  ⎿  (No output)

! ls -a /home/node/
  ⎿  .
     ..
     .bash_logout
     … +10 lines (ctrl+o to expand)


! ls -a /home/node/.claude/
  ⎿  .
     ..


! ls -a /home/yoh/.claude/
  ⎿  .
     ..
     .claude.json
     .claude.json.backup
     .credentials.json
     .git
     .npm
     CLAUDE.md
     CLAUDE.visidata.md
     agents

! touch /home/node/something
  ⎿  touch: cannot touch '/home/node/something': Permission denied

```

so due to `--userns=keep-id` (I believe) I am "myself" inside!  My HOME though is screwed up as pointing to current folder, and I cannot change anything under `/home/node` since it belongs not to me but to node:

```
! ls -l /home
  ⎿  total 4
     drwxr-xr-x 1 node node 166 Mar  1 09:11 node
     drwxr-xr-t 1 root root  30 Mar  2 18:52 yoh
```

since I do not think I care/want to keep any of those `~/.npm` etc around, most logical would be to prep/use some temp folder for the `$HOME`...

and I wonder if we should

- make `images/Dockerfile` to operate with the outside user identity instead of `node` so we just map the two identities into one somehow? (will not attempt trying ATM; let's figure your details).
  - if that doesn't work I would just create a temp folder to bind mount as HOME and populate with copy of files from `/home/node` for a good measure.
- indeed pass `--env HOME=$HOME` if still would be needed

### just-meng (2026-03-03T08:41:00Z)

> are you running on linux and is above your analysis or of claude as to state - Container user: node ($HOME=/home/node)?

yes, linux, no, did not set user to node myself

it likely boils down to the podman version running here: 4.3.1 (relatively old, from Ubuntu 22.04 repos). apparently, the --userns=keep-id behavior around HOME has changed across versions.

i have not confirmed yet that -e HOME fixes my problem (not allowed to run yolo --resume, because it won't start up a new container for the setting to take effect; and cannot trigger the auth request so i guess i wait ...)

### asmacdo (2026-03-03T12:30:09Z)

In the meantime for a workaround once you're logged in you can /resume to get to the previous conversations.

### yarikoptic (2026-03-03T14:36:15Z)

as for overall login workaround you can do what I do and described in [now folded comment](https://github.com/anthropics/claude-code/issues/1757#issuecomment-3811354846):

>  you need a dedicated run of claude setup-token to produce the one with duration of 1 year (seems to require providing it via `CLAUDE_CODE_OAUTH_TOKEN` env var.

and it would indeed be nice to "solidify" behavior around `HOME`.

### just-meng (2026-03-04T11:24:54Z)

Still getting the auth err:
```
  ⎿  API Error: 401
     {"type":"error","error":{"type":"authentication_error","message":"OAuth
     token has expired. Please obtain a new token or refresh your existing
     token."},"request_id":"req_011CYhwsYS2YK2i3ByTPGtLJ"} · Please run /login
```

After setting `-e HOME`:
```
podman run --log-driver=none -it --rm \
    --user="$(id -u):$(id -g)"\
    --userns=keep-id \
    --name="$name" \
    -v "$CLAUDE_MOUNT" \
    -v "$HOME/.gitconfig:/tmp/.gitconfig:ro,Z" \
    -v "$WORKSPACE_MOUNT" \
    "${WORKTREE_MOUNTS[@]}" \
    -w "$WORKSPACE_DIR" \
    -e HOME \
    -e CLAUDE_CONFIG_DIR="$CLAUDE_DIR" \
    -e GIT_CONFIG_GLOBAL=/tmp/.gitconfig \
    -e CLAUDE_CODE_OAUTH_TOKEN \
    -e CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS \
    "${NVIDIA_ARGS[@]}" \
    "${PODMAN_ARGS[@]}" \
    con-bomination-claude-code \
    "${CONTAINER_CMD[@]}"
```
For now I'll try with updating podman.

<details><summary>Full `~/.local/bin/yolo` here:  </summary>
```
#!/bin/bash
# Claude Code YOLO mode - auto-approve all actions in containerized environment

set -e

show_help() {
    cat << 'EOF'
Usage: yolo [OPTIONS] [-- CLAUDE_ARGS...]

Run Claude Code in YOLO mode (auto-approve all actions) inside a container.

OPTIONS:
    -h, --help           Show this help message
    --anonymized-paths   Use anonymized paths (/claude, /workspace) instead of
                         preserving host paths
    --entrypoint=CMD     Override the container entrypoint (default: claude)
    --worktree=MODE      Git worktree handling: ask, bind, skip, error
                         (default: ask)
    --nvidia             Enable NVIDIA GPU passthrough via CDI
                         Requires nvidia-container-toolkit on host
    --no-config          Ignore project configuration file
    --install-config     Create/display .git/yolo/config template

    Additional podman options can be passed before --

EXAMPLES:
    yolo                              # Basic usage
    yolo --nvidia                     # With GPU support
    yolo -v /data:/data               # Extra mount
    yolo -- "help with this code"     # Pass args to claude
    yolo --nvidia -- --resume         # GPU + claude args

NVIDIA GPU SETUP:
    The --nvidia flag uses CDI (Container Device Interface) for GPU access.
    Prerequisites:
    1. Install nvidia-container-toolkit on your host
    2. Generate CDI spec: sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
    3. Use: yolo --nvidia

PROJECT CONFIGURATION:
    Create .git/yolo/config to set per-project defaults.
    Run 'yolo --install-config' to create a template.

    The config file is a bash script that can set:
    - YOLO_PODMAN_VOLUMES: array of volume mounts
    - YOLO_PODMAN_OPTIONS: array of podman options
    - YOLO_CLAUDE_ARGS: array of arguments for claude
    - USE_ANONYMIZED_PATHS: 0 or 1
    - USE_NVIDIA: 0 or 1
    - WORKTREE_MODE: ask, bind, skip, or error

EOF
    exit 0
}

# Function to print the default config template
print_config_template() {
    cat << 'EOF'
# YOLO Project Configuration
# This file is sourced as a bash script by yolo
# Location: .git/yolo/config

# Volume mounts - array of volumes to mount
# Syntax options:
#   "~/projects"              -> ~/projects:~/projects:Z (1-to-1 mount)
#   "~/projects::ro"          -> ~/projects:~/projects:ro,Z (1-to-1 with options)
#   "~/data:/data:Z"          -> ~/data:/data:Z (explicit mapping)
YOLO_PODMAN_VOLUMES=(
    # "~/projects"
    # "~/data::ro"
)

# Additional podman options - array of options
YOLO_PODMAN_OPTIONS=(
    # "--env=DEBUG=1"
    # "--network=host"
)

# Claude arguments - array of arguments passed to claude
YOLO_CLAUDE_ARGS=(
    # "--model=claude-3-opus-20240229"
)

# Default flags (0 or 1)
# USE_ANONYMIZED_PATHS=0
# USE_NVIDIA=0
# WORKTREE_MODE="ask"
EOF
}

# Function to install config
install_config() {
    # Find .git directory
    local git_dir=""
    local current_dir="$(pwd)"

    while [ "$current_dir" != "/" ]; do
        if [ -d "$current_dir/.git" ]; then
            git_dir="$current_dir/.git"
            break
        elif [ -f "$current_dir/.git" ]; then
            # Worktree - read gitdir path
            local gitdir_line=$(cat "$current_dir/.git")
            if [[ "$gitdir_line" =~ ^gitdir:\ (.+)$ ]]; then
                local gitdir_path="${BASH_REMATCH[1]}"
                if [[ "$gitdir_path" != /* ]]; then
                    gitdir_path="$current_dir/$gitdir_path"
                fi
                if [[ "$gitdir_path" =~ ^(.+/\.git)/worktrees/ ]]; then
                    git_dir="${BASH_REMATCH[1]}"
                    break
                fi
            fi
        fi
        current_dir="$(dirname "$current_dir")"
    done

    if [ -z "$git_dir" ]; then
        echo "Error: Not in a git repository" >&2
        exit 1
    fi

    local config_dir="$git_dir/yolo"
    local config_file="$config_dir/config"

    if [ -f "$config_file" ]; then
        echo "Config file already exists at: $config_file"
        echo ""
        cat "$config_file"
    else
        mkdir -p "$config_dir"
        print_config_template > "$config_file"
        echo "Created config file at: $config_file"
        echo ""
        echo "Edit with: vi $config_file"
    fi

    exit 0
}

# Function to expand volume shorthand syntax
expand_volume() {
    local vol="$1"

    # Check for :: syntax first (shorthand with options)
    if [[ "$vol" == *::* ]]; then
        # Shorthand with options: ~/projects::ro,Z
        local path="${vol%%::*}"
        local opts="${vol#*::}"
        # Expand ~ to $HOME
        path="${path/#\~/$HOME}"
        echo "${path}:${path}:${opts}"
    elif [[ "$vol" == *:*:* ]]; then
        # Full form: host:container:options
        echo "$vol"
    elif [[ "$vol" == *:* ]]; then
        # Partial form: host:container (add :Z)
        echo "${vol}:Z"
    else
        # Shorthand: ~/projects
        # Expand ~ to $HOME and create 1-to-1 mapping
        local path="${vol/#\~/$HOME}"
        echo "${path}:${path}:Z"
    fi
}

# Parse arguments: everything before -- goes to podman, everything after goes to claude
# Also check for --anonymized-paths, --entrypoint, --worktree, --nvidia, --no-config, and --install-config flags
PODMAN_ARGS=()
CLAUDE_ARGS=()
found_separator=0
USE_ANONYMIZED_PATHS=0
ENTRYPOINT="claude"
WORKTREE_MODE="ask"
USE_NVIDIA=0
USE_CONFIG=1

# Initialize config arrays
YOLO_PODMAN_VOLUMES=()
YOLO_PODMAN_OPTIONS=()
YOLO_CLAUDE_ARGS=()

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help)
            show_help
            ;;
        --install-config)
            install_config
            ;;
        --entrypoint)
            ENTRYPOINT="$2"
            shift 2
            ;;
        --entrypoint=*)
            ENTRYPOINT="${1#--entrypoint=}"
            shift
            ;;
        --worktree=*)
            WORKTREE_MODE="${1#--worktree=}"
            # Validate worktree mode
            if [[ ! "$WORKTREE_MODE" =~ ^(ask|bind|skip|error)$ ]]; then
                echo "Error: Invalid --worktree value: $WORKTREE_MODE" >&2
                echo "Valid values are: ask, bind, skip, error" >&2
                exit 1
            fi
            shift
            ;;
        --anonymized-paths)
            USE_ANONYMIZED_PATHS=1
            shift
            ;;
        --nvidia)
            USE_NVIDIA=1
            shift
            ;;
        --no-config)
            USE_CONFIG=0
            shift
            ;;
        --)
            shift
            found_separator=1
            CLAUDE_ARGS=("$@")
            break
            ;;
        *)
            if [ "$found_separator" -eq 1 ]; then
                CLAUDE_ARGS+=("$1")
            else
                PODMAN_ARGS+=("$1")
            fi
            shift
            ;;
    esac
done

# Save original PODMAN_ARGS for later (before we potentially move them to CLAUDE_ARGS)
CLI_PODMAN_ARGS=("${PODMAN_ARGS[@]}")

if [ "$found_separator" = 0 ]; then
    # so we did not find any -- everything is actually CLAUDE_ARGS
    CLAUDE_ARGS=("${PODMAN_ARGS[@]}")
    PODMAN_ARGS=()
fi

# Load configuration if requested (after separator logic)
if [ "$USE_CONFIG" -eq 1 ]; then
    # Find .git directory
    git_dir=""
    current_dir="$(pwd)"

    while [ "$current_dir" != "/" ]; do
        if [ -d "$current_dir/.git" ]; then
            git_dir="$current_dir/.git"
            break
        elif [ -f "$current_dir/.git" ]; then
            # Worktree - read gitdir path
            gitdir_line=$(cat "$current_dir/.git")
            if [[ "$gitdir_line" =~ ^gitdir:\ (.+)$ ]]; then
                gitdir_path="${BASH_REMATCH[1]}"
                if [[ "$gitdir_path" != /* ]]; then
                    gitdir_path="$current_dir/$gitdir_path"
                fi
                if [[ "$gitdir_path" =~ ^(.+/\.git)/worktrees/ ]]; then
                    git_dir="${BASH_REMATCH[1]}"
                    break
                fi
            fi
        fi
        current_dir="$(dirname "$current_dir")"
    done

    if [ -n "$git_dir" ]; then
        config_dir="$git_dir/yolo"
        config_file="$config_dir/config"

        # Auto-create config directory and template on first run
        if [ ! -d "$config_dir" ]; then
            mkdir -p "$config_dir"
            print_config_template > "$config_file"
            echo "Created default config at: $config_file" >&2
            echo "Edit with: vi $config_file" >&2
            echo "" >&2
        fi

        if [ -f "$config_file" ]; then
            # Source the config file
            source "$config_file"

            # Process volumes and expand shorthand syntax
            for vol in "${YOLO_PODMAN_VOLUMES[@]}"; do
                expanded=$(expand_volume "$vol")
                PODMAN_ARGS=("-v" "$expanded" "${PODMAN_ARGS[@]}")
            done

            # Add podman options
            for opt in "${YOLO_PODMAN_OPTIONS[@]}"; do
                PODMAN_ARGS=("$opt" "${PODMAN_ARGS[@]}")
            done

            # Add claude args
            if [ ${#YOLO_CLAUDE_ARGS[@]} -gt 0 ]; then
                CLAUDE_ARGS=("${YOLO_CLAUDE_ARGS[@]}" "${CLAUDE_ARGS[@]}")
            fi
        fi
    fi
fi

# Give a meaningful name based on PWD and the PID to help identifying
# all those podman containers
# Note: leading periods and underscores are stripped as they're not allowed in container names
name=$( echo "$PWD-$$" | sed -e "s,^$HOME/,,g" -e "s,[^a-zA-Z0-9_.-],_,g" -e "s,^[._]*,," )

CLAUDE_HOME_DIR="$HOME/.claude"
# must exist but might not if first start on that box
mkdir -p "$CLAUDE_HOME_DIR"

# Detect if we're in a git worktree and find the original repo
WORKTREE_MOUNTS=()
gitdir_path=""
dot_git="$(pwd)/.git"
is_worktree=0
original_repo_dir=""

if [ -L "$dot_git" ]; then
    # .git is a symlink - resolve it to get the gitdir path
    gitdir_path=$(realpath "$dot_git" 2>/dev/null)
elif [ -f "$dot_git" ]; then
    # .git is a file, likely a worktree - read the gitdir path
    gitdir_line=$(cat "$dot_git")
    if [[ "$gitdir_line" =~ ^gitdir:\ (.+)$ ]]; then
        gitdir_path="${BASH_REMATCH[1]}"
        # Resolve to absolute path if relative
        if [[ "$gitdir_path" != /* ]]; then
            gitdir_path="$(pwd)/$gitdir_path"
        fi
        gitdir_path=$(realpath "$gitdir_path" 2>/dev/null || echo "$gitdir_path")
    fi
fi

if [ -n "$gitdir_path" ]; then
    # gitdir_path is typically /path/to/original/repo/.git/worktrees/<name>
    # We need to find the original repo's .git directory
    if [[ "$gitdir_path" =~ ^(.+/\.git)/worktrees/ ]]; then
        original_git_dir="${BASH_REMATCH[1]}"
        original_repo_dir=$(dirname "$original_git_dir")
        # Only consider it a worktree if it's different from our current workspace
        if [ "$original_repo_dir" != "$(pwd)" ]; then
            is_worktree=1
        fi
    fi
fi

# Handle worktree based on the mode
if [ "$is_worktree" -eq 1 ]; then
    case "$WORKTREE_MODE" in
        error)
            echo "Error: Running in a git worktree is not allowed with --worktree=error" >&2
            echo "Original repo: $original_repo_dir" >&2
            exit 1
            ;;
        bind)
            WORKTREE_MOUNTS+=("-v" "$original_repo_dir:$original_repo_dir:Z")
            ;;
        skip)
            # Do nothing - skip bind mount
            ;;
        ask)
            echo "Detected git worktree. Original repository: $original_repo_dir" >&2
            echo "Bind mounting the original repo allows git operations but may expose unintended files." >&2
            read -p "Bind mount original repository? [y/N] " -n 1 -r >&2
            echo >&2
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                WORKTREE_MOUNTS+=("-v" "$original_repo_dir:$original_repo_dir:Z")
            fi
            ;;
    esac
fi

# Determine paths based on --anonymized-paths flag
if [ "$USE_ANONYMIZED_PATHS" -eq 1 ]; then
    # Old behavior: use anonymized paths
    CLAUDE_DIR="/claude"
    WORKSPACE_DIR="/workspace"
    CLAUDE_MOUNT="$CLAUDE_HOME_DIR:/claude:Z"
    WORKSPACE_MOUNT="$(pwd):/workspace:Z"
else
    # New default behavior: preserve original host paths
    CLAUDE_DIR="$CLAUDE_HOME_DIR"
    WORKSPACE_DIR="$(pwd)"
    CLAUDE_MOUNT="$CLAUDE_HOME_DIR:$CLAUDE_HOME_DIR:Z"
    WORKSPACE_MOUNT="$(pwd):$(pwd):Z"
fi

# Build the command to run inside the container
if [ "$ENTRYPOINT" = "claude" ]; then
    # Default: run claude with --dangerously-skip-permissions
    CONTAINER_CMD=("claude" "--dangerously-skip-permissions" "${CLAUDE_ARGS[@]}")
else
    # Custom entrypoint: run as-is with any additional args
    CONTAINER_CMD=("$ENTRYPOINT" "${CLAUDE_ARGS[@]}")
fi

# NVIDIA GPU support via CDI (Container Device Interface)
# Requires nvidia-container-toolkit on host with CDI spec generated
NVIDIA_ARGS=()
if [ "$USE_NVIDIA" -eq 1 ]; then
    # Check if CDI spec exists
    if [ ! -f /etc/cdi/nvidia.yaml ] && [ ! -f /var/run/cdi/nvidia.yaml ]; then
        echo "Warning: NVIDIA CDI spec not found at /etc/cdi/nvidia.yaml or /var/run/cdi/nvidia.yaml" >&2
        echo "GPU passthrough may not work. Install nvidia-container-toolkit and run:" >&2
        echo "  sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml" >&2
        echo >&2
    fi
    NVIDIA_ARGS+=(--device "nvidia.com/gpu=all")
    NVIDIA_ARGS+=(--security-opt "label=disable")
fi

podman run --log-driver=none -it --rm \
    --user="$(id -u):$(id -g)"\
    --userns=keep-id \
    --name="$name" \
    -v "$CLAUDE_MOUNT" \
    -v "$HOME/.gitconfig:/tmp/.gitconfig:ro,Z" \
    -v "$WORKSPACE_MOUNT" \
    "${WORKTREE_MOUNTS[@]}" \
    -w "$WORKSPACE_DIR" \
    -e HOME \
    -e CLAUDE_CONFIG_DIR="$CLAUDE_DIR" \
    -e GIT_CONFIG_GLOBAL=/tmp/.gitconfig \
    -e CLAUDE_CODE_OAUTH_TOKEN \
    -e CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS \
    "${NVIDIA_ARGS[@]}" \
    "${PODMAN_ARGS[@]}" \
    con-bomination-claude-code \
    "${CONTAINER_CMD[@]}"
```
</details>

### just-meng (2026-03-04T11:41:20Z)

Now on podman version 4.6.2, still same behavior. When I look up `~/.claude/.credentials.json`, it contains `"expiresAt":1772583776416`. I suspect it is tied to my account/rate limited plan somehow that the token itself is valid only for a limited time.

### asmacdo (2026-03-06T17:33:40Z)

@just-meng once its working correctly, the token will still expire, but it should be able to renew itself IIRC

### yarikoptic (2026-03-12T15:57:24Z)

@just-meng original issue was about HOME mismatch -- have that one being found peace with so we could close? the other was credentials which relate likely to the issue I cited and generic to claude code -?

### just-meng (2026-03-12T16:51:51Z)

no it has not been resolved, still running as node despite the setting

### yarikoptic (2026-03-26T01:08:53Z)

BTW with #55 I provide a solution which forces `$HOME` to not correspond between host and container and to be `/home/node` (instead of CWD). And I think it is a good thing.  `CLAUDE_HOME_DIR="$HOME/.claude"` is defined outside of container and thus would remain mounted from original user's HOME, and have nothing to do with internal ~/ which would be largely empty anyways (besides what container provides for rudimentary user setup).

auth issue seems "upstream", as I mentioned
- https://github.com/anthropics/claude-code/issues/1757

and which I just overcame via providing a persistent token (although I think this way looses some features)

### just-meng (2026-03-27T16:43:52Z)

I had to get a primer on containers and UIDs from claude to understand what's happening here. And that's quite interesting. Let's see if I get it right:

Apparently my host UID is 1000 by default which is common for a single user on a Linux machine. That's likely not the case for you. Podman also uses UID 1000 by default and refers to this user as node. By accident, when I run yolo which sets --userns=keep-id, my host UID gets mapped into the container which happens to be found in in /etc/passwd due to the podman default user. So my home is set up correctly as /home/node, which means I never have seen any junk files as Yarik has reported. My home was truely ephemeral by accident. For any host UID other than 1000, a lookup in /etc/passwd won't find anything and the home gets set to the CWD which leaves a bunch of unwanted traces.

The fact that I had to re-login so often likely has nothing to do with the $HOME variable in the first place. Claude was misled by the node user. But this accidentally helped improving yolo in a different aspect!

### just-meng (2026-03-27T17:05:01Z)

And my new theory:

  - Token expires after 8 hours
  - While a session is running, Claude refreshes it silently ✓
  - When all sessions are closed, nothing is running to do the refresh
  - You sleep, token expires, no session to catch it
  - Morning: new session starts, token is stale, refresh fails on first message → 401

I always shut down my computer because it is too noisy. This likely explains the discrepancy we observe here. I'll try with the 1-year token.

### just-meng (2026-03-27T17:06:09Z)

Theory proven wrong! Token JUST expired mid-session.
