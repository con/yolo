# Design Decisions (Locked)

Decisions recorded here are final. Stop revisiting them.

## 1. Declarative config, not sourced bash

Config files must be declarative, not sourced as bash scripts. Sourced
bash means a committed `.yolo/config` in a cloned repo executes arbitrary
code on the host before the container starts — a prompt-injection vector
where a compromised agent poisons config for the next invocation.

## 2. Config format: YAML

YAML because:
- Scientists already read it (conda, Jupyter, CI files)
- Native arrays and nesting
- No arbitrary code execution
- Clean, readable syntax

No env var override mechanism — CLI flags already cover that use case.

## 3. Config file locations

Precedence (later overrides earlier):

1. `/etc/yolo/config.yaml` — system-wide (org defaults)
2. `${XDG_CONFIG_HOME:-~/.config}/yolo/config.yaml` — user preferences
3. `.yolo/config.yaml` — project, committed to git (shareable)
4. `.git/yolo/config.yaml` — project, local/untracked (personal)

CLI args override everything.

## 4. CLI in Python, distributed via PyPI

Package name: `con-yolo` (TODO: contact maintainers to get `yolo`).
Recommend install via `uv tool install con-yolo`.

Python because:
- Target users (scientists) already know it
- Contributors can read and modify it
- pytest for testing
- click/typer for CLI

## 5. Container-extras contract: one format, env vars

Every entry uses the `name:` form. All params become env vars
prefixed with `YOLO_{NAME}_{KEY}` uppercased:

```yaml
container-extras:
  - name: apt
    packages: [zsh, fzf]
  - name: python
    version: "3.12"
  - name: datalad
```

→ `YOLO_APT_PACKAGES="zsh fzf" bash apt.sh`
→ `YOLO_PYTHON_VERSION=3.12 bash python.sh`
→ `bash datalad.sh`

No prefix syntax (`apt:vim`), no simple dicts (`python: "3.12"`).
One format, one contract. Scripts validate their own env vars.

## 6. Container runtime: podman-first

Podman, specifically for rootless behavior (`--userns=keep-id`). The
architecture should allow other runtimes (docker, singularity/apptainer)
in the future, but podman is the starting point and the only one we
implement now.
