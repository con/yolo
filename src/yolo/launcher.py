"""Launch Claude Code in a container."""

import os
import subprocess
from pathlib import Path


def run() -> None:
    """Launch Claude Code in a podman container."""
    home = Path.home()
    cwd = Path.cwd()
    claude_dir = home / ".claude"
    claude_dir.mkdir(exist_ok=True)

    name = f"{cwd}-{os.getpid()}"
    name = name.replace(str(home) + "/", "")
    name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    name = name.lstrip("._")

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
        "-w",
        str(cwd),
        "-e",
        f"CLAUDE_CONFIG_DIR={claude_dir}",
        "-e",
        "GIT_CONFIG_GLOBAL=/tmp/.gitconfig",
        "-e",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "yolo-custom",
        "claude",
        "--dangerously-skip-permissions",
    ]

    subprocess.run(cmd)
