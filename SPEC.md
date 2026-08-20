# YOLO Specification

## Overview

YOLO runs Claude Code inside a rootless Podman container with
`--dangerously-skip-permissions`, relying on container isolation rather than
per-action approval to keep the host safe.

## Components

| Component            | Path             | Purpose                                            |
|----------------------|------------------|----------------------------------------------------|
| `bin/yolo`           | CLI wrapper      | Parses args, loads config, invokes `podman run`    |
| `setup-yolo.sh`      | Setup script     | Builds the container image and installs `bin/yolo` |
| `images/Dockerfile`  | Image definition | Development environment with Claude Code           |
| `config.example`     | Template         | Documented config file template                    |
| `tools/gpu-check.py` | GPU probe        | Verifies GPU passthrough without `nvidia-smi`      |

---

## 1. CLI: `bin/yolo`

### Usage

```
yolo [OPTIONS] [-- CLAUDE_ARGS...]
```

Everything before `--` is routed to podman. Everything after `--` is routed to
claude. If no `--` is present, all positional arguments go to claude.

### Flags

| Flag                 | Default  | Description                                              |
|----------------------|----------|----------------------------------------------------------|
| `-h`, `--help`       | —        | Show help and exit                                       |
| `--anonymized-paths` | off      | Use `/claude` and `/workspace` instead of host paths     |
| `--entrypoint=CMD`   | `claude` | Override container entrypoint                            |
| `--entrypoint CMD`   | `claude` | Same, space-separated form                               |
| `--tag=TAG`          | `latest` | Image tag to run (`con-bomination-claude-code:TAG`)      |
| `--tag TAG`          | `latest` | Same, space-separated form                               |
| `--worktree=MODE`    | `ask`    | Git worktree handling: `ask`, `bind`, `skip`, `error`    |
| `--nvidia`           | off      | Enable NVIDIA GPU passthrough via CDI                    |
| `--no-config`        | off      | Ignore all configuration files                           |
| `--install-config`   | —        | Create or display `.git/yolo/config` template, then exit |

### Argument Routing

1. Parse flags (`--help`, `--anonymized-paths`, etc.) consuming them from the argument list.
2. If `--` is found, everything after it becomes `CLAUDE_ARGS`.
3. Remaining arguments before `--` become `PODMAN_ARGS`.
4. If no `--` was found, all positional args are reassigned to `CLAUDE_ARGS` and `PODMAN_ARGS` is emptied.

---

## 2. Configuration System

### File Locations

| Scope       | Path                                        | Precedence |
|-------------|---------------------------------------------|------------|
| User-wide   | `${XDG_CONFIG_HOME:-~/.config}/yolo/config` | Lower      |
| Per-project | `.git/yolo/config`                          | Higher     |

Both files are sourced as bash scripts.

### Auto-creation

On first run in a git repo, if `.git/yolo/config` does not exist, it is
auto-created from the built-in template and a message is printed to stderr.

### Config Keys

#### Arrays (merged: user-wide + project)

| Key                   | Type       | Description                     |
|-----------------------|------------|---------------------------------|
| `YOLO_PODMAN_VOLUMES` | `string[]` | Volume mount specifications     |
| `YOLO_PODMAN_OPTIONS` | `string[]` | Additional `podman run` options |
| `YOLO_CLAUDE_ARGS`    | `string[]` | Arguments passed to claude      |

User-wide and project arrays are concatenated (user-wide first).

#### Scalars (project overrides user-wide)

| Key                    | Type     | Default  | Description                    | Precedence                     |
|------------------------|----------|----------|--------------------------------|--------------------------------|
| `USE_ANONYMIZED_PATHS` | `0\|1`   | `0`      | Use anonymized container paths | config overrides CLI           |
| `USE_NVIDIA`           | `0\|1`   | `0`      | Enable NVIDIA GPU passthrough  | config overrides CLI           |
| `WORKTREE_MODE`        | `string` | `ask`    | Git worktree handling mode     | config overrides CLI           |
| `YOLO_IMAGE_TAG`       | `string` | `latest` | Image tag to run               | CLI (`--tag`) overrides config |

Config files are sourced *after* the command line is parsed, so for
`USE_ANONYMIZED_PATHS`, `USE_NVIDIA`, and `WORKTREE_MODE` a value set in a
config file silently overrides the corresponding flag (e.g. `USE_NVIDIA=0` in
`.git/yolo/config` defeats `yolo --nvidia`). This is a known wart, not a
design goal.

`YOLO_IMAGE_TAG` is resolved explicitly after config loading instead: it may
also be set in the environment, config files override the environment, and
`--tag` overrides both. Tags must match `^[A-Za-z0-9_][A-Za-z0-9._-]*$`; an
invalid tag is a hard error.

### Loading Order

1. Parse CLI flags (sets initial scalar values; steps 2 and 5 can overwrite them).
2. Source user-wide config (if exists and `--no-config` not set).
3. Locate `.git` directory (traverses up from `$PWD`; handles worktrees).
4. Auto-create `.git/yolo/config` if `.git/yolo/` directory doesn't exist.
5. Source project config (if exists).
6. Merge arrays: `user-wide + project`.
7. Expand volumes via `expand_volume()` and prepend to `PODMAN_ARGS`.
8. Prepend `YOLO_PODMAN_OPTIONS` to `PODMAN_ARGS`.
9. Prepend `YOLO_CLAUDE_ARGS` to `CLAUDE_ARGS`.
10. Resolve the image tag: `--tag` if given, else `YOLO_IMAGE_TAG`, else `latest`.

---

## 3. Volume Mount Handling

### Shorthand Expansion (`expand_volume`)

| Input                   | Output                            | Rule                                          |
|-------------------------|-----------------------------------|-----------------------------------------------|
| `~/projects`            | `$HOME/projects:$HOME/projects:Z` | 1-to-1 with `:Z`                              |
| `~/data::ro`            | `$HOME/data:$HOME/data:ro`        | 1-to-1 with custom options (no `:Z` appended) |
| `/host:/container`      | `/host:/container:Z`              | Partial form, `:Z` appended                   |
| `/host:/container:opts` | `/host:/container:opts`           | Full form, passed through unchanged           |

Tilde (`~`) is expanded to `$HOME` in shorthand and `::` forms.

### Default Mounts

| Mount         | Host Path            | Container Path           | Options                |
|---------------|----------------------|--------------------------|------------------------|
| Claude home   | `~/.claude`          | `~/.claude` or `/claude` | `:z` (rw, shared)      |
| Git config    | `~/.gitconfig`       | `/tmp/.gitconfig`        | `ro,z` (shared)        |
| Workspace     | `$(pwd)`             | `$(pwd)` or `/workspace` | `:z` (rw, shared)      |
| Worktree repo | `$original_repo_dir` | `$original_repo_dir`     | `:z` (rw, conditional) |

Default mounts use lowercase `:z` (shared SELinux label) to allow multiple
concurrent yolo containers to access the same paths without EACCES errors.

The `~/.claude` directory is auto-created if missing.

---

## 4. Path Modes

### Preserved Paths (default)

| Variable          | Value                           |
|-------------------|---------------------------------|
| `CLAUDE_DIR`      | `$HOME/.claude`                 |
| `WORKSPACE_DIR`   | `$(pwd)`                        |
| `CLAUDE_MOUNT`    | `$HOME/.claude:$HOME/.claude:z` |
| `WORKSPACE_MOUNT` | `$(pwd):$(pwd):z`               |

Sessions are compatible between container and native Claude Code.

### Anonymized Paths (`--anonymized-paths`)

| Variable          | Value                     |
|-------------------|---------------------------|
| `CLAUDE_DIR`      | `/claude`                 |
| `WORKSPACE_DIR`   | `/workspace`              |
| `CLAUDE_MOUNT`    | `$HOME/.claude:/claude:z` |
| `WORKSPACE_MOUNT` | `$(pwd):/workspace:z`     |

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

| Mode    | Behavior                                      |
|---------|-----------------------------------------------|
| `ask`   | Prompt user; warn about security implications |
| `bind`  | Automatically mount original repo             |
| `skip`  | Do not mount original repo; continue normally |
| `error` | Exit with error if worktree detected          |

When mounted, the original repo is bind-mounted at its host path with `:z`.

---

## 6. Container Naming

```
name=$( echo "$PWD-$$" | sed -e "s,^$HOME/,,g" -e "s,[^a-zA-Z0-9_.-],_,g" -e "s,^[._]*,," )
```

- Strips `$HOME/` prefix.
- Replaces non-alphanumeric characters with `_`.
- Strips leading periods and underscores (not allowed by podman).
- Appends PID for uniqueness.

The generated name is used both as the podman container name (`--name`)
and as the claude session name (`claude --name`).

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

### Verifying Access (`tools/gpu-check.py`)

CDI injects the host's driver libraries and device nodes, but not the
`nvidia-smi` binary, so a container with working GPU access can still have no
CLI to confirm it. `tools/gpu-check.py` confirms it using only the Python
standard library (`ctypes`), so it needs no CUDA toolkit and no pip packages:

| Layer         | Source                       | Reports                                    |
|---------------|------------------------------|--------------------------------------------|
| Kernel driver | `/proc/driver/nvidia`, `/dev` | Driver version, device nodes, GPU model    |
| Telemetry     | `libnvidia-ml.so.1` (NVML)   | Utilization, memory, temperature, power    |
| Compute       | `libcuda.so.1` (driver API)  | The checks below                           |

Per-device compute checks, in order:

1. `context create` — `cuCtxCreate`.
2. `device allocation` — `cuMemAlloc` of `--alloc-mib` MiB (default 64).
3. `host<->device copy` — `cuMemcpyHtoD` + `cuMemcpyDtoH`, byte-compared.
4. `device-side memset` — `cuMemsetD32`, read back and verified.
5. `kernel launch` — a vector add JIT-compiled from PTX embedded in the script.
   The `.target` comes from the device's compute capability and the `.version`
   from the driver's CUDA version, so no toolkit and no pinned arch is involved.

Flags: `--json` (full report), `--quiet` (exit code only), `--alloc-mib N`.

| Exit code | Meaning                                       |
|-----------|-----------------------------------------------|
| 0         | GPU present and usable for compute            |
| 1         | GPU present but at least one check failed     |
| 2         | No GPU or driver visible in this container    |

---

## 8. Container Runtime

### Fixed `podman run` Arguments

| Argument       | Value                       | Purpose                         |
|----------------|-----------------------------|---------------------------------|
| `--log-driver` | `none`                      | No container logging            |
| `-it`          | —                           | Interactive + TTY               |
| `--rm`         | —                           | Auto-remove on exit             |
| `--userns`     | `keep-id:uid=1000,gid=1000` | Map host UID/GID to 1000 (node) |
| `--name`       | generated                   | Container name from PWD + PID   |
| `-w`           | `$WORKSPACE_DIR`            | Working directory               |

### Environment Variables

| Variable                               | Value             | Purpose                      |
|----------------------------------------|-------------------|------------------------------|
| `CLAUDE_CONFIG_DIR`                    | `$CLAUDE_DIR`     | Claude config location       |
| `GIT_CONFIG_GLOBAL`                    | `/tmp/.gitconfig` | Git identity                 |
| `CLAUDE_CODE_OAUTH_TOKEN`              | passthrough       | Auth token (if set on host)  |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | passthrough       | Agent teams (if set on host) |

### Container Command

| Entrypoint                | Command                                                 |
|---------------------------|---------------------------------------------------------|
| Default (`claude`)        | `claude --dangerously-skip-permissions [CLAUDE_ARGS]`   |
| Custom (`--entrypoint=X`) | `X [CLAUDE_ARGS]` (no `--dangerously-skip-permissions`) |

### Image

`con-bomination-claude-code:$IMAGE_TAG` (tag defaults to `latest`).

The tag comes from `--tag`, `YOLO_IMAGE_TAG` (config file or environment), or
`latest`. This allows test images built by `setup-yolo.sh --tag=TAG` to be run
side by side with the default one.

---

## 9. Container Image (`images/Dockerfile`)

### Base

`node:24-trixie` — Node 24 (current LTS) on Debian 13 "trixie".

The Debian release is pinned in the tag rather than tracking the rolling
`node:24` tag (still Debian 12 "bookworm"), so distro-conditional build steps
(the Apptainer package flavour) stay deterministic. Overridable
with the `BASE_IMAGE` build argument.

Notable versions from the base: git 2.47.3 (bookworm shipped 2.39, which lacks
`git worktree add --orphan`), Python 3.13, glibc 2.41.

### Init Process

`tini` (PID 1) — reaps zombie processes from forked children.

```
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["claude"]
```

### Non-root User

Runs as `node` user (UID 1000). Host UID mapped via `--userns=keep-id:uid=1000,gid=1000`.

### Core Packages

dnsutils, fzf, gh, git, gnupg2, iproute2, jq, less, man-db, mc, moreutils,
nano, ncdu, parallel, procps, shellcheck, sudo, tini, tree, unzip, vim, zsh

### Always-installed Tools

| Tool                | Install Method                                                    |
|---------------------|-------------------------------------------------------------------|
| Claude Code         | `npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}` |
| git-delta           | deb package from GitHub release (v0.18.2)                         |
| git-annex           | `uv tool install git-annex`                                       |
| uv                  | curl installer from astral.sh                                     |
| zsh + powerlevel10k | zsh-in-docker v1.2.0 with git, fzf plugins                        |

### Build Arguments

| Arg                     | Default          | Description                                                     |
|-------------------------|------------------|-----------------------------------------------------------------|
| `BASE_IMAGE`            | `node:24-trixie` | Base container image                                            |
| `TZ`                    | from host        | Timezone                                                        |
| `CLAUDE_CODE_VERSION`   | `latest`         | Claude Code npm version                                         |
| `EXTRA_PACKAGES`        | `""`             | Space-separated apt packages                                    |
| `EXTRA_PLAYWRIGHT`      | `""`             | Set to `"1"` to enable Playwright + Chromium                    |
| `EXTRA_DATALAD`         | `""`             | Set to `"1"` to enable DataLad                                  |
| `EXTRA_JJ`              | `""`             | Set to `"1"` to enable Jujutsu                                  |
| `EXTRA_DENO`            | `""`             | Set to `"1"` to enable Deno                                     |
| `EXTRA_ENTIRE`          | `""`             | Set to `"1"` to enable Entire CLI                               |
| `EXTRA_APPTAINER`       | `""`             | Set to `"1"` to enable Apptainer                                |
| `JJ_VERSION`            | `0.38.0`         | Jujutsu version                                                 |
| `DENO_VERSION`          | `""`             | Deno version (empty = latest)                                   |
| `APPTAINER_VERSION`     | `1.4.5`          | Apptainer version                                               |
| `GIT_DELTA_VERSION`     | `0.18.2`         | git-delta version                                               |
| `ZSH_IN_DOCKER_VERSION` | `1.2.0`          | zsh-in-docker version                                           |

### Optional Extras

| Extra        | What's Installed                                                                          |
|--------------|-------------------------------------------------------------------------------------------|
| `playwright` | System deps + `npm install -g playwright` + Chromium browser                              |
| `datalad`    | `uv tool install --with datalad-container --with datalad-next datalad`                    |
| `jj`         | Musl binary from GitHub release + zsh completion                                          |
| `deno`       | Deno JS/TS runtime via install script + zsh/bash PATH setup                               |
| `entire`     | Entire CLI via temporary Go toolchain install (`entireio/cli` v0.6.1)                     |
| `apptainer`  | Apptainer `.deb` from upstream GitHub release (amd64 only; bookworm/trixie auto-detected) |

No CUDA userspace is installed. GPU access is entirely a runtime concern —
`yolo --nvidia` injects the host driver via CDI (§7) — and shipping a toolkit
would risk shadowing those injected libraries with a mismatched userspace.

### Container Environment

| Variable            | Value                                                                         |
|---------------------|-------------------------------------------------------------------------------|
| `DEVCONTAINER`      | `true`                                                                        |
| `SHELL`             | `/bin/zsh`                                                                    |
| `EDITOR`            | `vim`                                                                         |
| `VISUAL`            | `vim`                                                                         |
| `NPM_CONFIG_PREFIX` | `/usr/local/share/npm-global`                                                 |
| `PATH`              | Includes npm-global/bin, `~/.local/bin`, `~/.deno/bin` |

---

## 10. Setup Script: `setup-yolo.sh`

### Usage

```
setup-yolo.sh [OPTIONS]
```

### Flags

| Flag                 | Default  | Values                         | Description                              |
|----------------------|----------|--------------------------------|------------------------------------------|
| `-h`, `--help`       | —        | —                              | Show help and exit                       |
| `--build=MODE`       | `auto`   | `auto`, `yes`, `no`            | Image build control                      |
| `--install=MODE`     | `auto`   | `auto`, `yes`, `no`            | Script install control                   |
| `--tag=TAG`          | `latest` | any valid image tag            | Tag to build/check                       |
| `--packages=PKGS`    | `""`     | comma/space-separated          | Extra apt packages                       |
| `--extras=EXTRAS`    | `""`     | comma-separated extras         | Predefined extras                        |
| `--base-image=IMAGE` | `""`     | image reference                | Override the base image                  |

Valid extras: `playwright`, `datalad`, `jj`, `deno`, `entire`, `apptainer`, and
`all` (expands to every extra above). `cuda` is also accepted and
`--cuda-version=VER` is parsed, but both are no-ops kept for backward
compatibility: they install nothing, are not passed to the build, and print a
note pointing at `yolo --nvidia`. `cuda` is not part of `all`.
Image tags must match `^[A-Za-z0-9_][A-Za-z0-9._-]*$`.

### Build Behavior

Existence checks, build (`podman build -t`), and all messages use the fully
qualified reference `con-bomination-claude-code:$IMAGE_TAG`, so each tag is
built and checked independently.

| Mode   | Image Exists | Image Missing |
|--------|--------------|---------------|
| `auto` | Skip         | Build         |
| `yes`  | Rebuild      | Build         |
| `no`   | OK           | Error         |

When a non-`latest` tag is used, the final message points at
`yolo --tag=TAG` for running the freshly built image.

### Install Behavior

Installs `bin/yolo` to `$HOME/.local/bin/yolo`.

| Mode   | Script Exists                        | Script Missing    |
|--------|--------------------------------------|-------------------|
| `auto` | Prompt if differs; skip if identical | Prompt to install |
| `yes`  | Overwrite                            | Install           |
| `no`   | Skip                                 | Skip              |

After install, checks if `~/.local/bin` is in `$PATH` and warns if not.

### Build Arguments Passed

- `TZ` from `timedatectl` (falls back to `UTC`).
- `CLAUDE_CACHEBUST` (current epoch seconds).
- `EXTRA_PACKAGES` (space-separated).
- `BASE_IMAGE` when non-empty.
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

| Mechanism      | Technology                           | What It Protects             |
|----------------|--------------------------------------|------------------------------|
| Filesystem     | Podman mount-only                    | Only mounted dirs visible    |
| User namespace | `--userns=keep-id:uid=1000,gid=1000` | No privilege escalation      |
| Process        | Rootless podman                      | Isolated from host processes |
| Network        | **None**                             | Unrestricted outbound access |

### Deliberate Non-restrictions

- Network access is unrestricted. The container can reach any host/port.
- `--dangerously-skip-permissions` auto-approves all Claude actions within the container.

---

## 12. Testing

### Framework

BATS (Bash Automated Testing System) with `bats-assert` and `bats-support`.

### Test Infrastructure

- `tests/yolo.bats` covers the CLI and setup script; `tests/gpu.bats` covers
  `tools/gpu-check.py`.
- Mock podman binary captures all arguments to a file for inspection.
- Isolated test environment: `$BATS_TEST_TMPDIR` with fake `$HOME`, git repo, and PATH.
- Helper functions: `run_yolo()`, `get_podman_args()`, `podman_args_contain()`, `refute_podman_arg()`, `write_user_config()`, `write_project_config()`.
- GPU helpers: `run_gpu_check()`, `has_gpu()`, `require_gpu()`, `require_python()`.
  Hardware-dependent tests `skip` where no GPU is visible, so `bats tests/`
  passes unchanged on CI runners and macOS.
- `bin/yolo` is sourceable without side effects via `BASH_SOURCE` guard.

### Test Coverage

- Volume expansion (shorthand, options, full form, partial form)
- All CLI flags (`--help`, `--no-config`, `--anonymized-paths`, `--nvidia`, `--entrypoint`, `--worktree`, `--tag`)
- Image tag resolution (default, `--tag`, `YOLO_IMAGE_TAG`, precedence, invalid tags)
- Argument routing (with and without `--` separator)
- Configuration loading and merging (user + project arrays, scalar overrides)
- `XDG_CONFIG_HOME` override
- Environment variable passthrough
- Container naming
- Config template generation
- `tools/gpu-check.py`: stdlib-only imports, `--help`, `--json` shape, exit
  status matching GPU presence, and the no-driver path (stubbed, so it is
  covered on GPU hosts too)
- On real hardware only: driver reporting, `--alloc-mib`, and every compute
  check passing

---

## 13. CI/CD

### Triggers

- Push to `main` or `enhs`.
- Pull requests targeting `main`.

### Jobs

| Job         | Runner                      | What It Does                                      |
|-------------|-----------------------------|---------------------------------------------------|
| ShellCheck  | ubuntu-latest               | Lints `setup-yolo.sh` and `bin/yolo`              |
| Unit Tests  | ubuntu-latest, macos-latest | Runs BATS test suite                              |
| Test Setup  | ubuntu-latest               | Builds image via `setup-yolo.sh`, verifies syntax |
| Integration | ubuntu-latest               | Full build + `podman run --rm ... claude --help`  |

Integration test depends on ShellCheck and Test Setup passing.
