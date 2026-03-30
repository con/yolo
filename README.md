# yolo

Run Claude Code safely in a rootless Podman container with full autonomy.

## Prerequisites

- [Podman](https://podman.io/docs/installation) (rootless)
- Python 3.11+

## Install

<!-- ```bash
pip install con-yolo
``` -->

```bash
uv tool install "con-yolo @ git+https://github.com/asmacdo/yolo@redesign-python"
```

## Quick start

```bash
cd your-project
yo run
```

That's it. First run builds the image automatically, then drops you
into Claude Code with full autonomy inside a container.

Customize your project with `yo init` to create a `.yolo/config.yaml`:

```bash
yo init
```

Try the interactive demo:

```bash
yo demo
```

## Git worktrees

When running in a git worktree, `yo run` detects it and asks whether
to bind-mount the original repository (needed for git operations like
commit and fetch). Control with `--worktree=ask|bind|skip|error` or
set `worktree:` in config.

**Security note**: binding the original repo exposes more files than
the worktree alone.

## TODO

- [ ] Configuration reference

## Image extras

Builtin extras: `apt`, `python`, `git-delta`, `pip`, `datalad`, `jj`,
`playwright`.

Write your own — drop a bash script in `.yolo/image-extras/` or
`~/.config/yolo/image-extras/` and reference it by name in your config:

```yaml
images:
  - name: default
    extras:
      - name: my-tool
```

Scripts are self-contained bash. See `image-extras/` for examples.

## Security

yolo runs Claude Code with `--dangerously-skip-permissions` — the
container is the sandbox. Isolation is provided by rootless Podman:

- **Filesystem**: only `~/.claude`, `~/.gitconfig`, and your working
  directory are mounted. No SSH keys, no cloud credentials.
- **Process**: rootless Podman with `--userns=keep-id` — user namespace
  isolation, not real root on the host.
- **Config**: YAML only, not sourced bash. Config can't execute code.

**Not restricted:**

- **Network**: containers have full network access (package registries,
  APIs, etc.). This is a known gap.

**When to be cautious:**

- Untrusted repositories — prompt injection via code comments or docs
  could trick Claude into exfiltrating data over the network.
- Mounting directories with sensitive data (credentials, private keys).
- Projects that access production systems or databases.
- **Config as escape vector**: Claude can edit `.yolo/config.yaml` or
  `.git/yolo/config.yaml` inside the container. A modified config takes
  effect on the next `yo run` — e.g. adding volume mounts to expose
  host paths. The `.git/` location is especially easy to miss. Review
  config changes after sessions with untrusted code.

See SPEC.md § Security for the full threat model.

## Development install

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

Or to put `yo` on your PATH globally without a venv:

```bash
uv tool install -e .
```
