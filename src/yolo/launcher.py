"""Launch Claude Code in a container."""

import os
import re
import subprocess
import sys
from pathlib import Path

from yolo.builder import build, image_tag
from yolo.config import load_config


def _expand_volume(vol: str) -> str:
    """Expand volume shorthand to full podman -v syntax.

    ~/projects         → $HOME/projects:$HOME/projects:z
    ~/data::ro         → $HOME/data:$HOME/data:ro
    /host:/container   → /host:/container:z
    /host:/cont:opts   → /host:/cont:opts  (unchanged)
    """
    home = str(Path.home())
    if "::" in vol:
        path, _, opts = vol.partition("::")
        path = path.replace("~", home, 1)
        return f"{path}:{path}:{opts}"
    elif vol.count(":") >= 2:
        return vol
    elif ":" in vol:
        return f"{vol}:z"
    else:
        path = vol.replace("~", home, 1)
        return f"{path}:{path}:z"


def _build_volume_args(volumes: list[str]) -> list[str]:
    """Turn a list of volume specs into podman -v args."""
    args = []
    for vol in volumes:
        args.extend(["-v", _expand_volume(vol)])
    return args


def _nvidia_args(enabled: bool) -> list[str]:
    """Return podman args for NVIDIA GPU passthrough."""
    if not enabled:
        return []
    cdi_paths = [Path("/etc/cdi/nvidia.yaml"), Path("/var/run/cdi/nvidia.yaml")]
    if not any(p.exists() for p in cdi_paths):
        print(
            "Warning: NVIDIA CDI spec not found. GPU passthrough may not work.\n"
            "  sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml",
            file=sys.stderr,
        )
    return ["--device", "nvidia.com/gpu=all", "--security-opt", "label=disable"]


def _build_env_args(env_config: list[str]) -> list[str]:
    """Build -e args from env config.

    Bare name = passthrough from host. KEY=VALUE = set explicitly.
    """
    args = []
    for entry in env_config:
        args.extend(["-e", entry])
    return args


def _detect_worktree() -> Path | None:
    """If cwd is a git worktree, return the original repo dir."""
    dot_git = Path.cwd() / ".git"

    if dot_git.is_symlink():
        gitdir_path = dot_git.resolve()
    elif dot_git.is_file():
        text = dot_git.read_text().strip()
        if not text.startswith("gitdir: "):
            return None
        gitdir_path = Path(text[len("gitdir: ") :])
        if not gitdir_path.is_absolute():
            gitdir_path = Path.cwd() / gitdir_path
        gitdir_path = gitdir_path.resolve()
    else:
        return None

    match = re.match(r"^(.+/\.git)/worktrees/", str(gitdir_path))
    if not match:
        return None

    original_repo = Path(match.group(1)).parent
    if original_repo == Path.cwd():
        return None

    return original_repo


def _worktree_volume(mode: str) -> list[str]:
    """Handle worktree detection and return extra volume args."""
    original = _detect_worktree()
    if original is None:
        return []

    if mode == "error":
        print(
            f"Error: Running in a git worktree is not allowed (original: {original})",
            file=sys.stderr,
        )
        sys.exit(1)
    elif mode == "skip":
        return []
    elif mode == "bind":
        return ["-v", f"{original}:{original}:z"]
    elif mode == "ask":
        print(
            f"Detected git worktree. Original repository: {original}", file=sys.stderr
        )
        print(
            "Bind mounting the original repo allows git operations but may expose unintended files.",
            file=sys.stderr,
        )
        reply = input("Bind mount original repository? [y/N] ")
        if reply.strip().lower() == "y":
            return ["-v", f"{original}:{original}:z"]
        return []
    else:
        print(f"Warning: unknown worktree mode '{mode}', skipping", file=sys.stderr)
        return []


def run(
    claude_args: list[str] | None = None,
    extra_volumes: list[str] | None = None,
    entrypoint: str | None = None,
    image_name: str | None = None,
    worktree: str | None = None,
    nvidia: bool = False,
    container_args: list[str] | None = None,
    no_config: bool = False,
) -> None:
    """Launch Claude Code in a podman container."""
    config = load_config(no_config=no_config)
    worktree_mode = worktree or config.get("worktree", "ask")
    use_nvidia = nvidia or config.get("nvidia", False)

    home = Path.home()
    cwd = Path.cwd()
    claude_dir = home / ".claude"
    claude_dir.mkdir(exist_ok=True)
    clip_dir = home / ".local" / "share" / "yolo" / "clip"
    clip_dir.mkdir(parents=True, exist_ok=True)

    name = f"{cwd}-{os.getpid()}"
    name = name.replace(str(home) + "/", "")
    name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    name = name.lstrip("._")

    tag = image_tag(image_name or "default")
    result = subprocess.run(["podman", "image", "exists", tag], capture_output=True)
    if result.returncode != 0:
        print(f"Image {tag} not found, building...", file=sys.stderr)
        build(config.get("images", []), only=image_name)

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
        "-v",
        f"{clip_dir}:/tmp/yolo-clip:z",
        *_build_volume_args(config_volumes),
        *_build_volume_args(extra_volumes or []),
        *_worktree_volume(worktree_mode),
        *_nvidia_args(use_nvidia),
        *(container_args or []),
        "-w",
        str(cwd),
        "-e",
        f"CLAUDE_CONFIG_DIR={claude_dir}",
        "-e",
        "GIT_CONFIG_GLOBAL=/tmp/.gitconfig",
        *_build_env_args(config.get("env", [])),
        tag,
    ]

    context_lines = config.get("context", [])
    context_args = []
    if context_lines:
        context_args = ["--append-system-prompt", "\n".join(context_lines)]

    # TODO: make dangerously_skip_permissions a separate config value
    # so --entrypoint claude doesn't automatically get it
    if entrypoint:
        cmd += [entrypoint, *(claude_args or [])]
    else:
        cmd += [
            "claude",
            "--dangerously-skip-permissions",
            *context_args,
            *(claude_args or []),
        ]

    subprocess.run(cmd)
