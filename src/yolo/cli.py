"""CLI entry point for yolo."""

import shutil
import subprocess
from pathlib import Path

import click

from yolo.builder import build as builder_build
from yolo.config import load_config
from yolo.launcher import run as launcher_run

CONFIG_TEMPLATE = Path(__file__).parent / "defaults" / "config.template.yaml"


@click.group()
@click.option(
    "--no-config", is_flag=True, default=False, help="Ignore all config files"
)
@click.pass_context
def main(ctx, no_config):
    """Run Claude Code safely in a container with full autonomy."""
    ctx.ensure_object(dict)
    ctx.obj["no_config"] = no_config


@main.command()
@click.option("--image", default=None, help="Build only this named image")
@click.option("--verify", is_flag=True, default=False, help="Run extras in verify mode")
@click.pass_context
def build(ctx, image, verify):
    """Build the container image with configured extras."""
    config = load_config(no_config=ctx.obj["no_config"])
    images = config.get("images", [])
    builder_build(images, only=image, verify=verify)


@main.command()
@click.option("--local", "target", flag_value="local", help="Write to .git/yolo/")
@click.option("--user", "target", flag_value="user", help="Write to ~/.config/yolo/")
@click.option("--path", "custom_path", default=None, help="Write to custom location")
@click.option(
    "--project",
    "target",
    flag_value="project",
    default=True,
    help="Write to .yolo/ (default)",
)
def init(target, custom_path):
    """Create a config file from the default template."""
    if custom_path:
        dest = Path(custom_path) / "config.yaml"
    elif target == "local":
        from yolo.config import _find_git_dir

        git_dir = _find_git_dir()
        if not git_dir:
            raise click.ClickException("Not in a git repository")
        dest = git_dir / "yolo" / "config.yaml"
    elif target == "user":
        import os

        xdg = os.environ.get("XDG_CONFIG_HOME", "")
        base = Path(xdg) if xdg else Path.home() / ".config"
        dest = base / "yolo" / "config.yaml"
    else:
        dest = Path.cwd() / ".yolo" / "config.yaml"

    if dest.exists():
        click.echo(f"Config already exists: {dest}")
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CONFIG_TEMPLATE, dest)
    click.echo(f"Created {dest}")


@main.command()
@click.pass_context
def clip(ctx):
    """Copy container clipboard content to host clipboard."""
    clip_file = Path.home() / ".local" / "share" / "yolo" / "clip" / "content"
    if not clip_file.exists():
        raise click.ClickException("Nothing to clip (no content written yet)")
    config = load_config(no_config=ctx.obj["no_config"])
    clipboard_cmd = config.get("host_clipboard_command", "xclip -selection clipboard")
    content = clip_file.read_text()
    subprocess.run(clipboard_cmd.split(), input=content, text=True, check=True)
    click.echo(f"Copied {len(content)} chars to clipboard")


@main.command()
def demo():
    """Run the interactive yolo demo."""
    import os

    demo_dir = Path(__file__).resolve().parent.parent.parent / "demo"
    if not (demo_dir / "demo.md").exists():
        raise click.ClickException(f"Demo not found at {demo_dir}")
    os.chdir(demo_dir)
    launcher_run(["Read demo.md and follow it."])


@main.command(context_settings={"ignore_unknown_options": True})
@click.option(
    "-v", "--volume", multiple=True, help="Extra bind mount (host:container[:opts])"
)
@click.option("--entrypoint", default=None, help="Override container entrypoint")
@click.option("--image", default=None, help="Run a specific named image")
@click.option(
    "--worktree",
    type=click.Choice(["ask", "bind", "skip", "error"]),
    default=None,
    help="Git worktree handling mode",
)
@click.option(
    "--nvidia",
    is_flag=True,
    default=False,
    help="Enable NVIDIA GPU passthrough via CDI",
)
@click.option(
    "--container-arg",
    multiple=True,
    help="Pass raw arg to container engine (repeatable)",
)
@click.argument("claude_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def run(ctx, volume, entrypoint, image, worktree, nvidia, container_arg, claude_args):
    """Launch Claude Code in a container."""
    launcher_run(
        list(claude_args),
        no_config=ctx.obj["no_config"],
        extra_volumes=list(volume),
        entrypoint=entrypoint,
        image_name=image,
        worktree=worktree,
        nvidia=nvidia,
        container_args=list(container_arg),
    )
