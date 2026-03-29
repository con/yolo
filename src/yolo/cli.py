"""CLI entry point for yolo."""

import click

from yolo.config import load_config
from yolo.builder import build as builder_build
from yolo.launcher import run as launcher_run


@click.group()
def main():
    """Run Claude Code safely in a container with full autonomy."""


@main.command()
def build():
    """Build the container image with configured extras."""
    config = load_config()
    extras = config.get("container-extras", [])
    builder_build(extras)


@main.command(context_settings={"ignore_unknown_options": True})
@click.option(
    "-v", "--volume", multiple=True, help="Extra bind mount (host:container[:opts])"
)
@click.argument("claude_args", nargs=-1, type=click.UNPROCESSED)
def run(volume, claude_args):
    """Launch Claude Code in a container."""
    launcher_run(list(claude_args), extra_volumes=list(volume))
