**Before writing files, check if CLAUDE.md, design docs, or tests need updating to reflect your changes.**

## Project

yolo runs Claude Code safely in a rootless Podman container with full autonomy.

Currently being rewritten from bash to Python. Legacy code is in `legacy/`.

## Key files

- `design/HACK_DECISIONS.md` — locked design decisions, do not revisit
- `design/REDESIGN_HACKIN.md` — working design notes
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

- `src/yolo/config.py` — YAML config loading from 4 locations
- `src/yolo/cli.py` — click CLI (yo build, yo run)
- `images/Containerfile.base` — minimal debian base image
- `images/Containerfile.extras` — layers container-extras on top
- `container-extras/` — composable install scripts (apt.sh, python.sh, etc.)
