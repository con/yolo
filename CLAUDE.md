**Before writing files, check if CLAUDE.md, design docs, or tests need updating to reflect your changes.**

## Python

- Always import at the top of the file unless there's a good reason not to.

## Project

yolo runs Claude Code safely in a rootless Podman container with full autonomy.

Currently being rewritten from bash to Python. Legacy code is in `design/legacy/`.

## Key files

- `SPEC.md` — current specification (source of truth for behavior)
- `design/HACK_DECISIONS.md` — locked design decisions, do not revisit
- `design/LEGACY_SPEC.md` — spec of the legacy bash implementation
- `tests/features_to_test.md` — checklist of things that need tests

## Development

```
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest
```

Entry point is `yo` (temporary, becomes `yolo` at cutover).

## Architecture

- `src/yolo/config.py` — YAML config loading from 5 locations (defaults + 4 user)
- `src/yolo/builder.py` — resolves extras, assembles build context, invokes podman
- `src/yolo/cli.py` — click CLI (yo build, yo run)
- `src/yolo/launcher.py` — assembles podman run command
- `src/yolo/defaults/config.yaml` — default image-extras shipped with package
- `images/Containerfile.base` — minimal debian base image
- `images/Containerfile.extras` — layers image-extras on top
- `image-extras/` — composable install scripts (apt.sh, python.sh, etc.)
- `.local-notes/` — gitignored local working notes (issues, PRs, etc.)
