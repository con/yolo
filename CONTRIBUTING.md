# Contributing

## Setup

```
git clone https://github.com/con/yolo
cd yolo
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pre-commit install
```

## Running tests

```
pytest
```

## Pre-commit hooks

Hooks run automatically on commit:
- **ruff** — Python lint and format
- **yamllint** — YAML validation
- **shellcheck** — shell script lint

Run manually against all files:

```
pre-commit run --all-files
```

## Writing image-extras scripts

Scripts live in `image-extras/`. Each script is a self-contained
bash installer. Parameters are passed as env vars prefixed with
`YOLO_{SCRIPTNAME}_{KEY}`:

```bash
#!/bin/bash
# Env: YOLO_APT_PACKAGES (required)
set -eu
[ -z "${YOLO_APT_PACKAGES:-}" ] && { echo "apt.sh: YOLO_APT_PACKAGES required"; exit 1; }
sudo apt-get install -y $YOLO_APT_PACKAGES
```

Config references scripts by name:

```yaml
image-extras:
  - name: apt
    packages: [zsh, fzf]
```

See `design/HACK_DECISIONS.md` for the full contract.
