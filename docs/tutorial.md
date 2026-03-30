# yolo tutorial — Python rewrite

You know the bash yolo. This is the same idea — Claude Code in a rootless
Podman container with `--dangerously-skip-permissions` — rebuilt as a
Python package with YAML config instead of sourced shell scripts.

## 1. Install

```bash
cd /path/to/yolo
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

The entry point is `yo` (becomes `yolo` at cutover).

## 2. yo init — generate a config

CLAUDE WE JUST CHANGED INIT REGENERATE THIS SECTION

```bash
cd ~/my-project
yo init
```


Creates `.yolo/config.yaml` from the built-in template:

CLAUDE BUT SHOWING THE DEFAULT YAML IS STILL COOL

```yaml
env:
  - CLAUDE_CODE_OAUTH_TOKEN
  - CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS

images:
  - name: default
    extras:
      - name: apt
        packages: [fzf, gh, less, man-db, shellcheck, zsh]
      - name: git-delta
        version: "0.18.2"
      - name: python
        version: "3.12"
```

Other targets: `yo init --user` (`~/.config/yolo/`),
`yo init --local` (`.git/yolo/`, untracked).

## 3. yo build — build the image

```bash
yo build
```

Output shows what's about to happen before the build starts:

```
  Image: yolo-my-project-default
  Base:  yolo-base
  Extras:
    - apt (/path/to/yolo/image-extras)
    - git-delta (/path/to/yolo/image-extras)
    - python (/path/to/yolo/image-extras)
```

First build also builds `yolo-base` (debian + Claude Code + tini).

## 4. yo run — launch Claude

```bash
yo run
```

That's it. You're in a container running
`claude --dangerously-skip-permissions`. Workspace is bind-mounted rw.

Pass args through to Claude:

```bash
yo run -- --model sonnet
```
CLAUDE WE HAVE A BUILTINS SHOW HOW TO USE THOSE FIRST AND INTRODUCE CUSTOM SCRIPTS LATER
WHEN YOU DO YOU CAN ALSO CASUALLY MENTION THAT IF GENERALLY USEFUL CONSIDER ADDING IT TO YOLO

## 5. Customize: add an extras script

Extras are self-contained bash scripts. Add one to your project:

```bash
mkdir -p .yolo/image-extras
```
CLAUDE WE HAVE AN APT BUILTIN FOR CUSTOM SHOW SOMETHING NOT APT, MAYBE EVEN NOT AN INSTALL IDK

```bash
cat > .yolo/image-extras/datalad.sh << 'EOF'
#!/bin/bash
# Install datalad
set -eu
sudo apt-get install -y --no-install-recommends datalad
EOF
```

Add it to your config:

```yaml
images:
  - name: default
    extras:
      - name: apt
        packages: [fzf, gh, less, man-db, shellcheck, zsh]
      - name: git-delta
        version: "0.18.2"
      - name: python
        version: "3.12"
      - name: datalad
```

## 6. Rebuild and verify

```bash
yo build
yo run --entrypoint bash
```

`--entrypoint` overrides the container command (skips
`--dangerously-skip-permissions`). Poke around:

```bash
which datalad
datalad --version
exit
```

CLAUDE LETS MAKE A SHORT SECTION THATS LIKE HEY ITS AT PARITY THESE OTHER FEATURES STILL WORK

## 7. Volume shorthand

Add extra bind mounts in config:

```yaml
volumes:
  - ~/data                # → ~/data:~/data:z
  - ~/datasets::ro        # → ~/datasets:~/datasets:ro
  - /scratch:/scratch     # → /scratch:/scratch:z
```

Or on the command line:

```bash
yo run -v ~/data -v /scratch:/scratch
```

## 8. NVIDIA GPU passthrough

In config:

```yaml
nvidia: true
```

Or per-run:

```bash
yo run --nvidia
```

Requires NVIDIA CDI spec (`sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml`).

## 9. Git worktree handling

If you run from a git worktree, yolo can bind-mount the original repo
so git operations work inside the container.

```yaml
worktree: bind    # always mount original repo
# worktree: ask   # prompt (default)
# worktree: skip  # ignore worktree
# worktree: error # refuse to run
```

Or per-run:

```bash
yo run --worktree bind
```

## 10. Key differences from legacy

| Legacy (bash) | Rewrite (Python) |
|---|---|
| Sourced shell config | YAML config — declarative, no injection risk |
| Single hardcoded image | Named images with `from:` composition |
| Extras baked into Containerfile | Composable scripts, 4-level search path |
| Flags in env vars | Proper CLI (`yo build`, `yo run`) |
| One config location | 5-layer merge (package → system → user → project → local) |

### Config layering

Later layers override earlier ones. Lists append, dicts merge, scalars replace.

```
0. Package defaults (built-in)
1. /etc/yolo/config.yaml         — org-wide
2. ~/.config/yolo/config.yaml    — your preferences
3. .yolo/config.yaml             — project (committed)
4. .git/yolo/config.yaml         — project (local, untracked)
```

### Image composition with `from:`

Stack images using Podman's native `FROM`:

```yaml
images:
  - name: default
    extras:
      - name: apt
        packages: [zsh, fzf]
      - name: python
        version: "3.12"

  - name: heavy
    from: yolo-my-project-default
    extras:
      - name: cuda
```

Build a specific image:

```bash
yo build --image heavy
yo run --image heavy
```
