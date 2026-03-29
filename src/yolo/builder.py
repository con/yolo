"""Build container images with image-extras."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONTAINERFILE_EXTRAS = REPO_ROOT / "images" / "Containerfile.extras"
BUILTIN_EXTRAS = REPO_ROOT / "image-extras"

BASE_IMAGE = "yolo-base"


def _project_dirname() -> str:
    """Get project dirname from git toplevel or cwd."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip()).name
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd().name


def image_tag(image_name: str) -> str:
    """Derive podman image tag from image name."""
    project = _project_dirname()
    project = "".join(c if c.isalnum() or c in "-_" else "-" for c in project)
    return f"yolo-{project}-{image_name}"


def _extras_search_path() -> list[Path]:
    """Return image-extras directories in precedence order (lowest first)."""
    paths = [BUILTIN_EXTRAS]

    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        paths.append(Path(xdg) / "yolo" / "image-extras")
    else:
        paths.append(Path.home() / ".config" / "yolo" / "image-extras")

    paths.append(Path.cwd() / ".yolo" / "image-extras")

    from yolo.config import _find_git_dir

    git_dir = _find_git_dir()
    if git_dir:
        paths.append(git_dir / "yolo" / "image-extras")

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
    """Parse a single image-extras entry into (name, env_vars).

    Entry must be a dict with a 'name' key, or a string (name only):
      {"name": "apt", "packages": "zsh fzf"}  -> ("apt", {"YOLO_APT_PACKAGES": "zsh fzf"})
      {"name": "python", "version": "3.12"}   -> ("python", {"YOLO_PYTHON_VERSION": "3.12"})
      {"name": "datalad"}                      -> ("datalad", {})
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


def _image_exists(tag: str) -> bool:
    """Check if a podman image exists locally."""
    result = subprocess.run(
        ["podman", "image", "exists", tag],
        capture_output=True,
    )
    return result.returncode == 0


def _build_base() -> None:
    """Build yolo-base from Containerfile.base."""
    containerfile = REPO_ROOT / "images" / "Containerfile.base"
    print(f"Building {BASE_IMAGE}...")
    subprocess.run(
        [
            "podman",
            "build",
            "-f",
            str(containerfile),
            "-t",
            BASE_IMAGE,
            str(REPO_ROOT / "images"),
        ],
        check=True,
    )
    print(f"Built {BASE_IMAGE}")


def _ensure_base(base: str, images_config: list) -> None:
    """Ensure a base image exists. Build it if we know how."""
    if _image_exists(base):
        return

    if base == BASE_IMAGE:
        _build_base()
        return

    # Check if it's an image defined in our config
    for entry in images_config:
        name = entry.get("name", "default")
        if image_tag(name) == base:
            build_image(entry, images_config)
            return

    raise RuntimeError(f"Base image '{base}' not found and not defined in config")


def build_image(image_entry: dict, images_config: list | None = None) -> str:
    """Build a single image from an images list entry. Returns the tag."""
    name = image_entry.get("name", "default")
    extras = image_entry.get("extras", [])
    tag = image_tag(name)

    if not extras:
        print(f"No extras for image '{name}', skipping.")
        return tag

    base = image_entry.get("from", BASE_IMAGE)
    _ensure_base(base, images_config or [])

    build_dir = assemble_build_context(extras)
    try:
        cmd = [
            "podman",
            "build",
            "--build-arg",
            f"BASE_IMAGE={base}",
            "-f",
            str(CONTAINERFILE_EXTRAS),
            "-t",
            tag,
            str(build_dir),
        ]
        print(f"Building {tag}...")
        subprocess.run(cmd, check=True)
        print(f"Built {tag}")
    finally:
        shutil.rmtree(build_dir)

    return tag


def build(images_config: list, only: str | None = None) -> None:
    """Build images from config. Optionally filter by name."""
    if not images_config:
        print("No images configured, nothing to build.")
        return

    for entry in images_config:
        name = entry.get("name", "default")
        if only and name != only:
            continue
        build_image(entry, images_config)
