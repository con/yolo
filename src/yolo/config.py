"""Load and merge YAML config from all locations."""

from pathlib import Path
import os
import subprocess

from ruamel.yaml import YAML


CONFIG_FILENAME = "config.yaml"
DEFAULTS_CONFIG = Path(__file__).parent / "defaults" / CONFIG_FILENAME
_yaml = YAML()
_yaml.preserve_quotes = True

# Precedence: later overrides earlier
# 0. Package defaults (src/yolo/defaults/config.yaml)
# 1. /etc/yolo/config.yaml
# 2. ~/.config/yolo/config.yaml (XDG)
# 3. .yolo/config.yaml (project, committed)
# 4. .git/yolo/config.yaml (project, local)


def _find_git_dir() -> Path | None:
    """Walk up from cwd to find .git directory, handling worktrees."""
    current = Path.cwd()
    while current != current.parent:
        dot_git = current / ".git"
        if dot_git.is_dir():
            return dot_git
        if dot_git.is_file():
            # Worktree — parse gitdir: line
            text = dot_git.read_text().strip()
            if text.startswith("gitdir: "):
                gitdir = Path(text[len("gitdir: "):])
                if not gitdir.is_absolute():
                    gitdir = current / gitdir
                gitdir = gitdir.resolve()
                # Extract the main .git dir from .git/worktrees/<name>
                for parent in gitdir.parents:
                    if parent.name == ".git":
                        return parent
        current = current.parent
    return None


def _config_paths() -> list[Path]:
    """Return config file paths in precedence order (lowest first)."""
    paths = [Path("/etc/yolo") / CONFIG_FILENAME]

    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        paths.append(Path(xdg) / "yolo" / CONFIG_FILENAME)
    else:
        paths.append(Path.home() / ".config" / "yolo" / CONFIG_FILENAME)

    # Project configs
    project_root = Path.cwd()
    paths.append(project_root / ".yolo" / CONFIG_FILENAME)

    git_dir = _find_git_dir()
    if git_dir:
        paths.append(git_dir / "yolo" / CONFIG_FILENAME)

    return paths


def _load_yaml(path: Path) -> dict:
    """Load a YAML file, returning empty dict if missing or empty."""
    if not path.is_file():
        return {}
    data = _yaml.load(path)
    return dict(data) if data else {}


def _merge(base: dict, override: dict) -> dict:
    """Merge override into base. Lists append, dicts recurse, scalars replace."""
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], list) and isinstance(value, list):
            merged[key] = merged[key] + value
        elif key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config() -> dict:
    """Load and merge config from all locations."""
    config = _load_yaml(DEFAULTS_CONFIG)
    for path in _config_paths():
        layer = _load_yaml(path)
        if layer:
            config = _merge(config, layer)
    return config
