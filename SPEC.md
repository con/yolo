# YOLO Specification

## Overview

YOLO runs Claude Code inside a rootless Podman container with
`--dangerously-skip-permissions`, relying on container isolation rather than
per-action approval to keep the host safe.

## Components

| Component          | Path             | Purpose                                          |
|--------------------|------------------|--------------------------------------------------|
| `bin/yolo`         | CLI wrapper      | Parses args, loads config, invokes `podman run`   |
| `setup-yolo.sh`    | Setup script     | Builds the container image and installs `bin/yolo` |
| `images/Dockerfile` | Image definition | Development environment with Claude Code          |
| `config.example`   | Template         | Documented config file template                   |

---

## 1. CLI: `bin/yolo`

### Usage

```
yolo [OPTIONS] [-- CLAUDE_ARGS...]
```

Everything before `--` is routed to podman. Everything after `--` is routed to
claude. If no `--` is present, all positional arguments go to claude.

### Flags

| Flag                 | Default  | Description                                                  |
|----------------------|----------|--------------------------------------------------------------|
| `-h`, `--help`       | —        | Show help and exit                                           |
| `--anonymized-paths` | off      | Use `/claude` and `/workspace` instead of host paths         |
| `--entrypoint=CMD`   | `claude` | Override container entrypoint                                |
| `--entrypoint CMD`   | `claude` | Same, space-separated form                                   |
| `--worktree=MODE`    | `ask`    | Git worktree handling: `ask`, `bind`, `skip`, `error`        |
| `--nvidia`           | off      | Enable NVIDIA GPU passthrough via CDI                        |
| `--no-config`        | off      | Ignore all configuration files                               |
| `--install-config`   | —        | Create or display `.git/yolo/config` template, then exit     |

### Argument Routing

1. Parse flags (`--help`, `--anonymized-paths`, etc.) consuming them from the argument list.
2. If `--` is found, everything after it becomes `CLAUDE_ARGS`.
3. Remaining arguments before `--` become `PODMAN_ARGS`.
4. If no `--` was found, all positional args are reassigned to `CLAUDE_ARGS` and `PODMAN_ARGS` is emptied.

---

## 2. Configuration System

### File Locations

| Scope       | Path                                       | Precedence |
|-------------|--------------------------------------------|------------|
| User-wide   | `${XDG_CONFIG_HOME:-~/.config}/yolo/config` | Lower      |
| Per-project | `.git/yolo/config`                          | Higher     |

Both files are sourced as bash scripts.

### Auto-creation

On first run in a git repo, if `.git/yolo/config` does not exist, it is
auto-created from the built-in template and a message is printed to stderr.

### Config Keys

#### Arrays (merged: user-wide + project)

| Key                    | Type       | Description                        |
|------------------------|------------|------------------------------------|
| `YOLO_PODMAN_VOLUMES`  | `string[]` | Volume mount specifications        |
| `YOLO_PODMAN_OPTIONS`  | `string[]` | Additional `podman run` options    |
| `YOLO_CLAUDE_ARGS`     | `string[]` | Arguments passed to claude         |

User-wide and project arrays are concatenated (user-wide first).

#### Scalars (project overrides user-wide; CLI overrides both)

| Key                    | Type     | Default | Description                    |
|------------------------|----------|---------|--------------------------------|
| `USE_ANONYMIZED_PATHS` | `0\|1`   | `0`     | Use anonymized container paths |
| `USE_NVIDIA`           | `0\|1`   | `0`     | Enable NVIDIA GPU passthrough  |
| `WORKTREE_MODE`        | `string` | `ask`   | Git worktree handling mode     |

### Loading Order

1. Parse CLI flags (sets defaults and overrides).
2. Source user-wide config (if exists and `--no-config` not set).
3. Locate `.git` directory (traverses up from `$PWD`; handles worktrees).
4. Auto-create `.git/yolo/config` if `.git/yolo/` directory doesn't exist.
5. Source project config (if exists).
6. Merge arrays: `user-wide + project`.
7. Expand volumes via `expand_volume()` and prepend to `PODMAN_ARGS`.
8. Prepend `YOLO_PODMAN_OPTIONS` to `PODMAN_ARGS`.
9. Prepend `YOLO_CLAUDE_ARGS` to `CLAUDE_ARGS`.

---

## 3. Volume Mount Handling

### Shorthand Expansion (`expand_volume`)

| Input                   | Output                              | Rule                                         |
|-------------------------|-------------------------------------|----------------------------------------------|
| `~/projects`            | `$HOME/projects:$HOME/projects:Z`   | 1-to-1 with `:Z`                             |
| `~/data::ro`            | `$HOME/data:$HOME/data:ro`          | 1-to-1 with custom options (no `:Z` appended) |
| `/host:/container`      | `/host:/container:Z`                | Partial form, `:Z` appended                  |
| `/host:/container:opts` | `/host:/container:opts`             | Full form, passed through unchanged          |

Tilde (`~`) is expanded to `$HOME` in shorthand and `::` forms.

### Default Mounts

| Mount         | Host Path            | Container Path               | Options              |
|---------------|----------------------|------------------------------|----------------------|
| Claude home   | `~/.claude`          | `~/.claude` or `/claude`     | `:Z` (rw)            |
| Git config    | `~/.gitconfig`       | `/tmp/.gitconfig`            | `ro,Z`               |
| Workspace     | `$(pwd)`             | `$(pwd)` or `/workspace`     | `:Z` (rw)            |
| Worktree repo | `$original_repo_dir` | `$original_repo_dir`         | `:Z` (rw, conditional) |

The `~/.claude` directory is auto-created if missing.

---

## 4. Path Modes

### Preserved Paths (default)

| Variable          | Value                           |
|-------------------|---------------------------------|
| `CLAUDE_DIR`      | `$HOME/.claude`                 |
| `WORKSPACE_DIR`   | `$(pwd)`                        |
| `CLAUDE_MOUNT`    | `$HOME/.claude:$HOME/.claude:Z` |
| `WORKSPACE_MOUNT` | `$(pwd):$(pwd):Z`               |

Sessions are compatible between container and native Claude Code.

### Anonymized Paths (`--anonymized-paths`)

| Variable          | Value                      |
|-------------------|----------------------------|
| `CLAUDE_DIR`      | `/claude`                  |
| `WORKSPACE_DIR`   | `/workspace`               |
| `CLAUDE_MOUNT`    | `$HOME/.claude:/claude:Z`  |
| `WORKSPACE_MOUNT` | `$(pwd):/workspace:Z`      |

All projects appear at `/workspace`, enabling cross-project session context.

---

## 5. Git Worktree Support

### Detection

1. If `.git` is a symlink: resolve via `realpath`.
2. If `.git` is a file: parse `gitdir: <path>` line.
3. Resolve relative gitdir paths to absolute.
4. Match pattern `^(.+/\.git)/worktrees/` to identify worktree.
5. Only flag as worktree if original repo dir differs from `$(pwd)`.

### Handling Modes

| Mode    | Behavior                                         |
|---------|--------------------------------------------------|
| `ask`   | Prompt user; warn about security implications    |
| `bind`  | Automatically mount original repo                |
| `skip`  | Do not mount original repo; continue normally    |
| `error` | Exit with error if worktree detected             |

When mounted, the original repo is bind-mounted at its host path with `:Z`.

---

## 6. Container Naming

```
name=$( echo "$PWD-$$" | sed -e "s,^$HOME/,,g" -e "s,[^a-zA-Z0-9_.-],_,g" -e "s,^[._]*,," )
```

- Strips `$HOME/` prefix.
- Replaces non-alphanumeric characters with `_`.
- Strips leading periods and underscores (not allowed by podman).
- Appends PID for uniqueness.

---

## 7. NVIDIA GPU Support

### Prerequisites

1. `nvidia-container-toolkit` installed on host.
2. CDI spec generated: `sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml`.

### Behavior

When `USE_NVIDIA=1`:

1. Check for CDI spec at `/etc/cdi/nvidia.yaml` or `/var/run/cdi/nvidia.yaml`.
2. Warn to stderr if not found (does not fail).
3. Add `--device nvidia.com/gpu=all` to podman args.
4. Add `--security-opt label=disable` to allow GPU device access with SELinux.

---

## 8. Container Runtime

### Fixed `podman run` Arguments

| Argument       | Value                | Purpose                            |
|----------------|----------------------|------------------------------------|
| `--log-driver` | `none`               | No container logging               |
| `-it`          | —                    | Interactive + TTY                  |
| `--rm`         | —                    | Auto-remove on exit                |
| `--user`       | `$(id -u):$(id -g)`  | Run as host user                   |
| `--userns`     | `keep-id`            | Map host user ID into container    |
| `--name`       | generated            | Container name from PWD + PID      |
| `-w`           | `$WORKSPACE_DIR`     | Working directory                  |

### Environment Variables

| Variable                                 | Value              | Purpose                       |
|------------------------------------------|--------------------|-------------------------------|
| `CLAUDE_CONFIG_DIR`                      | `$CLAUDE_DIR`      | Claude config location        |
| `GIT_CONFIG_GLOBAL`                      | `/tmp/.gitconfig`  | Git identity                  |
| `CLAUDE_CODE_OAUTH_TOKEN`                | passthrough        | Auth token (if set on host)   |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`   | passthrough        | Agent teams (if set on host)  |

### Container Command

| Entrypoint               | Command                                                    |
|--------------------------|------------------------------------------------------------|
| Default (`claude`)       | `claude --dangerously-skip-permissions [CLAUDE_ARGS]`      |
| Custom (`--entrypoint=X`) | `X [CLAUDE_ARGS]` (no `--dangerously-skip-permissions`)    |

### Image

`con-bomination-claude-code`

---

## 9. Container Image (`images/Dockerfile`)

### Base

`node:22`

### Init Process

`tini` (PID 1) — reaps zombie processes from forked children.

```
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["claude"]
```

### Non-root User

Runs as `node` user (UID typically 1000). Host UID mapped via `--userns=keep-id`.

### Core Packages

dnsutils, fzf, gh, git, gnupg2, iproute2, jq, less, man-db, mc, moreutils,
nano, ncdu, parallel, procps, shellcheck, sudo, tini, tree, unzip, vim, zsh

### Always-installed Tools

| Tool                 | Install Method                                                |
|----------------------|---------------------------------------------------------------|
| Claude Code          | `npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}` |
| git-delta            | deb package from GitHub release (v0.18.2)                     |
| git-annex            | `uv tool install git-annex`                                   |
| uv                   | curl installer from astral.sh                                 |
| zsh + powerlevel10k  | zsh-in-docker v1.2.0 with git, fzf plugins                   |

### Build Arguments

| Arg                    | Default  | Description                                |
|------------------------|----------|--------------------------------------------|
| `TZ`                   | from host | Timezone                                   |
| `CLAUDE_CODE_VERSION`  | `latest` | Claude Code npm version                    |
| `EXTRA_PACKAGES`       | `""`     | Space-separated apt packages               |
| `EXTRA_CUDA`           | `""`     | Set to `"1"` to enable CUDA toolkit        |
| `EXTRA_PLAYWRIGHT`     | `""`     | Set to `"1"` to enable Playwright + Chromium |
| `EXTRA_DATALAD`        | `""`     | Set to `"1"` to enable DataLad             |
| `EXTRA_JJ`             | `""`     | Set to `"1"` to enable Jujutsu             |
| `JJ_VERSION`           | `0.38.0` | Jujutsu version                            |
| `GIT_DELTA_VERSION`    | `0.18.2` | git-delta version                          |
| `ZSH_IN_DOCKER_VERSION` | `1.2.0`  | zsh-in-docker version                      |

### Optional Extras

| Extra        | What's Installed                                                        |
|--------------|-------------------------------------------------------------------------|
| `cuda`       | `nvidia-cuda-toolkit` (enables non-free/contrib apt sources)            |
| `playwright` | System deps + `npm install -g playwright` + Chromium browser            |
| `datalad`    | `uv tool install --with datalad-container --with datalad-next datalad`  |
| `jj`         | Musl binary from GitHub release + zsh completion                        |

### Container Environment

| Variable             | Value                          |
|----------------------|--------------------------------|
| `DEVCONTAINER`       | `true`                         |
| `SHELL`              | `/bin/zsh`                     |
| `EDITOR`             | `vim`                          |
| `VISUAL`             | `vim`                          |
| `NPM_CONFIG_PREFIX`  | `/usr/local/share/npm-global`  |
| `PATH`               | Includes npm-global/bin, `~/.local/bin` |

---

## 10. Setup Script: `setup-yolo.sh`

### Usage

```
setup-yolo.sh [OPTIONS]
```

### Flags

| Flag               | Default | Values                                       | Description            |
|--------------------|---------|----------------------------------------------|------------------------|
| `-h`, `--help`     | —       | —                                            | Show help and exit     |
| `--build=MODE`     | `auto`  | `auto`, `yes`, `no`                          | Image build control    |
| `--install=MODE`   | `auto`  | `auto`, `yes`, `no`                          | Script install control |
| `--packages=PKGS`  | `""`    | comma/space-separated                        | Extra apt packages     |
| `--extras=EXTRAS`  | `""`    | `cuda`, `playwright`, `datalad`, `jj`, `all` | Predefined extras      |

### Build Behavior

| Mode   | Image Exists | Image Missing |
|--------|--------------|---------------|
| `auto` | Skip         | Build         |
| `yes`  | Rebuild      | Build         |
| `no`   | OK           | Error         |

### Install Behavior

Installs `bin/yolo` to `$HOME/.local/bin/yolo`.

| Mode   | Script Exists                          | Script Missing     |
|--------|----------------------------------------|--------------------|
| `auto` | Prompt if differs; skip if identical   | Prompt to install  |
| `yes`  | Overwrite                              | Install            |
| `no`   | Skip                                   | Skip               |

After install, checks if `~/.local/bin` is in `$PATH` and warns if not.

### Build Arguments Passed

- `TZ` from `timedatectl` (falls back to `UTC`).
- `EXTRA_PACKAGES` (space-separated).
- Each extra as `EXTRA_$(UPPERCASE)=1`.

---

## 11. Security Boundaries

### Mounted (accessible inside container)

- `~/.claude` — credentials, session history (read-write)
- `~/.gitconfig` — git identity (read-only)
- `$(pwd)` — current project (read-write)
- Additional volumes from `YOLO_PODMAN_VOLUMES` config
- Original git repo (only if worktree mode permits)

### Not Mounted (inaccessible)

- `~/.ssh` — SSH keys (prevents `git push` by design)
- `~/.gnupg` — GPG keys (unless explicitly mounted)
- `~/.aws`, `~/.kube`, etc. — cloud credentials
- Rest of the filesystem

### Isolation Mechanisms

| Mechanism        | Technology         | What It Protects               |
|------------------|--------------------|--------------------------------|
| Filesystem       | Podman mount-only  | Only mounted dirs visible      |
| User namespace   | `--userns=keep-id` | No privilege escalation        |
| Process          | Rootless podman    | Isolated from host processes   |
| Network          | **None**           | Unrestricted outbound access   |

### Deliberate Non-restrictions

- Network access is unrestricted. The container can reach any host/port.
- `--dangerously-skip-permissions` auto-approves all Claude actions within the container.

---

## 12. Testing

### Framework

BATS (Bash Automated Testing System) with `bats-assert` and `bats-support`.

### Test Infrastructure

- Mock podman binary captures all arguments to a file for inspection.
- Isolated test environment: `$BATS_TEST_TMPDIR` with fake `$HOME`, git repo, and PATH.
- Helper functions: `run_yolo()`, `get_podman_args()`, `podman_args_contain()`, `refute_podman_arg()`, `write_user_config()`, `write_project_config()`.
- `bin/yolo` is sourceable without side effects via `BASH_SOURCE` guard.

### Test Coverage

- Volume expansion (shorthand, options, full form, partial form)
- All CLI flags (`--help`, `--no-config`, `--anonymized-paths`, `--nvidia`, `--entrypoint`, `--worktree`)
- Argument routing (with and without `--` separator)
- Configuration loading and merging (user + project arrays, scalar overrides)
- `XDG_CONFIG_HOME` override
- Environment variable passthrough
- Container naming
- Config template generation

---

## 13. CI/CD

### Triggers

- Push to `main`.
- Pull requests targeting `main`.

### Jobs

| Job          | Runner                      | What It Does                                         |
|--------------|-----------------------------|------------------------------------------------------|
| ShellCheck   | ubuntu-latest               | Lints `setup-yolo.sh` and `bin/yolo`                 |
| Unit Tests   | ubuntu-latest, macos-latest | Runs BATS test suite                                 |
| Test Setup   | ubuntu-latest               | Builds image via `setup-yolo.sh`, verifies syntax    |
| Integration  | ubuntu-latest               | Full build + `podman run --rm ... claude --help`     |

Integration test depends on ShellCheck and Test Setup passing.
