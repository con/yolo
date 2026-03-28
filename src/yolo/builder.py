"""Build container images with container-extras."""

import shutil
import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONTAINERFILE_EXTRAS = REPO_ROOT / "images" / "Containerfile.extras"
BUILTIN_EXTRAS = REPO_ROOT / "container-extras"

BASE_IMAGE = "yolo-base"
CUSTOM_IMAGE = "yolo-custom"


def _extras_search_path() -> list[Path]:
    """Return container-extras directories in precedence order (lowest first)."""
    import os

    paths = [BUILTIN_EXTRAS]

    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        paths.append(Path(xdg) / "yolo" / "container-extras")
    else:
        paths.append(Path.home() / ".config" / "yolo" / "container-extras")

    paths.append(Path.cwd() / ".yolo" / "container-extras")

    from yolo.config import _find_git_dir

    git_dir = _find_git_dir()
    if git_dir:
        paths.append(git_dir / "yolo" / "container-extras")

    return paths


def _resolve_script(name: str, search_path: list[Path]) -> Path | None:
    """Find a script by name in the search path. Later paths win."""
    found = None
    for directory in search_path:
        candidate = directory / f"{name}.sh"
        if candidate.is_file():
            found = candidate
    return found


def _parse_extra(entry) -> tuple[str, dict[str, str]]:
    """Parse a single container-extras entry into (name, env_vars).

    Entry must be a dict with a 'name' key, or a string (name only):
      {"name": "apt", "packages": "zsh fzf"}  → ("apt", {"YOLO_APT_PACKAGES": "zsh fzf"})
      {"name": "python", "version": "3.12"}   → ("python", {"YOLO_PYTHON_VERSION": "3.12"})
      {"name": "datalad"}                      → ("datalad", {})
    """
    if isinstance(entry, str):
        return (entry, {})

    if not isinstance(entry, dict) or "name" not in entry:
        raise ValueError(f"Invalid container-extra: {entry!r} (must have 'name' key)")

    name = entry["name"]
    env_vars = {}
    for key, value in entry.items():
        if key == "name":
            continue
        env_key = f"YOLO_{name}_{key}".upper().replace("-", "_")
        if isinstance(value, list):
            env_vars[env_key] = " ".join(str(v) for v in value)
        else:
            env_vars[env_key] = str(value)

    return (name, env_vars)


def assemble_build_context(extras_config: list) -> Path:
    """Create a temp directory with scripts and run.sh for podman build.

    Returns the path to the temp directory. Caller must clean up.
    """
    search_path = _extras_search_path()

    build_dir = Path(tempfile.mkdtemp(prefix="yolo-build-"))
    scripts_dir = build_dir / "build" / "scripts"
    scripts_dir.mkdir(parents=True)

    run_lines = ["#!/bin/bash", "set -eu"]

    for entry in extras_config:
        name, env_vars = _parse_extra(entry)

        script = _resolve_script(name, search_path)
        if script is None:
            raise FileNotFoundError(
                f"No script found for '{name}' in search path: "
                + ", ".join(str(p) for p in search_path)
            )

        dest = scripts_dir / f"{name}.sh"
        if not dest.exists():
            shutil.copy2(script, dest)

        env_prefix = " ".join(f'{k}="{v}"' for k, v in env_vars.items())
        if env_prefix:
            run_lines.append(f"{env_prefix} bash /tmp/yolo-build/scripts/{name}.sh")
        else:
            run_lines.append(f"bash /tmp/yolo-build/scripts/{name}.sh")

    run_sh = build_dir / "build" / "run.sh"
    run_sh.write_text("\n".join(run_lines) + "\n")

    return build_dir


def build(extras_config: list) -> None:
    """Build the custom image with container-extras."""
    if not extras_config:
        print("No container-extras configured, nothing to build.")
        return

    build_dir = assemble_build_context(extras_config)
    try:
        cmd = [
            "podman", "build",
            "-f", str(CONTAINERFILE_EXTRAS),
            "-t", CUSTOM_IMAGE,
            str(build_dir),
        ]
        print(f"Building {CUSTOM_IMAGE}...")
        subprocess.run(cmd, check=True)
        print(f"Built {CUSTOM_IMAGE}")
    finally:
        shutil.rmtree(build_dir)
