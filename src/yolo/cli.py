"""CLI entry point for yolo."""

import click

from yolo.builder import build as builder_build
from yolo.config import load_config
from yolo.launcher import run as launcher_run


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
@click.pass_context
def build(ctx, image):
    """Build the container image with configured extras."""
    config = load_config(no_config=ctx.obj["no_config"])
    images = config.get("images", [])
    builder_build(images, only=image)


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
