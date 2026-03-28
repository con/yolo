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

    # .git/yolo/container-extras
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


def _parse_extras(extras_config: list) -> list[tuple[str, list[str]]]:
    """Parse container-extras config into (script_name, args) pairs.

    Config entries can be:
      - "datalad"              → ("datalad", [])
      - "apt:imagemagick"      → ("apt", ["imagemagick"])
      - {"python": "3.12"}     → ("python", ["3.12"])
    """
    parsed = []
    for entry in extras_config:
        if isinstance(entry, str):
            if ":" in entry:
                prefix, _, arg = entry.partition(":")
                parsed.append((prefix, [arg]))
            else:
                parsed.append((entry, []))
        elif isinstance(entry, dict):
            for name, args in entry.items():
                if isinstance(args, list):
                    parsed.append((name, [str(a) for a in args]))
                else:
                    parsed.append((name, [str(args)]))
    return parsed


def _collect_apt_fallbacks(
    parsed: list[tuple[str, list[str]]], search_path: list[Path]
) -> list[tuple[str, list[str]]]:
    """For bare names with no matching script, convert to apt calls."""
    result = []
    apt_packages = []

    for name, args in parsed:
        script = _resolve_script(name, search_path)
        if script or args:
            # Has a script or is a prefixed entry — flush any pending apt packages
            if apt_packages:
                result.append(("apt", apt_packages))
                apt_packages = []
            result.append((name, args))
        else:
            # No script found, no prefix — accumulate as apt package
            apt_packages.append(name)

    if apt_packages:
        result.append(("apt", apt_packages))

    return result


def assemble_build_context(extras_config: list) -> Path:
    """Create a temp directory with scripts and run.sh for podman build.

    Returns the path to the temp directory. Caller must clean up.
    """
    search_path = _extras_search_path()
    parsed = _parse_extras(extras_config)
    resolved = _collect_apt_fallbacks(parsed, search_path)

    build_dir = Path(tempfile.mkdtemp(prefix="yolo-build-"))
    scripts_dir = build_dir / "build" / "scripts"
    scripts_dir.mkdir(parents=True)

    run_lines = ["#!/bin/bash", "set -eu"]

    for name, args in resolved:
        script = _resolve_script(name, search_path)
        if script is None:
            raise FileNotFoundError(
                f"No script found for '{name}' in search path: "
                + ", ".join(str(p) for p in search_path)
            )

        dest = scripts_dir / f"{name}.sh"
        if not dest.exists():
            shutil.copy2(script, dest)

        args_str = " ".join(args)
        if args_str:
            run_lines.append(f"bash /tmp/yolo-build/scripts/{name}.sh {args_str}")
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
