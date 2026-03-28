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


@main.command()
def run():
    """Launch Claude Code in a container."""
    launcher_run()
