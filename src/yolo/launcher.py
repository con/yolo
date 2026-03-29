"""Launch Claude Code in a container."""

import os
import subprocess
from pathlib import Path

from yolo.builder import image_tag
from yolo.config import load_config


def _build_volume_args(volumes: list[str]) -> list[str]:
    """Turn a list of volume specs into podman -v args."""
    # TODO: rename to mounts? these are bind mounts, not docker volumes
    args = []
    for vol in volumes:
        args.extend(["-v", vol])
    return args


def run(
    claude_args: list[str] | None = None,
    extra_volumes: list[str] | None = None,
    entrypoint: str | None = None,
    image_name: str | None = None,
) -> None:
    """Launch Claude Code in a podman container."""
    config = load_config()

    home = Path.home()
    cwd = Path.cwd()
    claude_dir = home / ".claude"
    claude_dir.mkdir(exist_ok=True)

    name = f"{cwd}-{os.getpid()}"
    name = name.replace(str(home) + "/", "")
    name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    name = name.lstrip("._")

    config_volumes = config.get("volumes", [])

    cmd = [
        "podman",
        "run",
        "--log-driver=none",
        "-it",
        "--rm",
        f"--user={os.getuid()}:{os.getgid()}",
        "--userns=keep-id",
        f"--name={name}",
        "-v",
        f"{claude_dir}:{claude_dir}:z",
        "-v",
        f"{home}/.gitconfig:/tmp/.gitconfig:ro,z",
        "-v",
        f"{cwd}:{cwd}:z",
        *_build_volume_args(config_volumes),
        *_build_volume_args(extra_volumes or []),
        "-w",
        str(cwd),
        "-e",
        f"CLAUDE_CONFIG_DIR={claude_dir}",
        "-e",
        "GIT_CONFIG_GLOBAL=/tmp/.gitconfig",
        "-e",
        "CLAUDE_CODE_OAUTH_TOKEN",
        image_tag(image_name or "default"),
    ]

    # TODO: make dangerously_skip_permissions a separate config value
    # so --entrypoint claude doesn't automatically get it
    if entrypoint:
        cmd += [entrypoint, *(claude_args or [])]
    else:
        cmd += ["claude", "--dangerously-skip-permissions", *(claude_args or [])]

    subprocess.run(cmd)
