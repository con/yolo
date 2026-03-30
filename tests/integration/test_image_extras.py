"""Integration tests for image-extras scripts.

Each script in image-extras/ must support YOLO_VERIFY=1 mode.
Tests build an image through the normal Containerfile.extras path,
then verify inside the built image.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from yolo.builder import assemble_build_context

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
IMAGE_EXTRAS_DIR = REPO_ROOT / "image-extras"
CONTAINERFILE_EXTRAS = REPO_ROOT / "images" / "Containerfile.extras"
BASE_IMAGE = "yolo-base"


def _get_extra_scripts():
    return sorted(IMAGE_EXTRAS_DIR.glob("*.sh"))


def _script_ids():
    return [s.stem for s in _get_extra_scripts()]


def _verify_config(script):
    """Build a config entry that runs the script in verify mode."""
    return [{"name": script.stem}]


@pytest.fixture(scope="module", autouse=True)
def ensure_base_image():
    result = subprocess.run(
        ["podman", "image", "exists", BASE_IMAGE],
        capture_output=True,
    )
    if result.returncode != 0:
        subprocess.run(
            [
                "podman",
                "build",
                "-f",
                str(REPO_ROOT / "images" / "Containerfile.base"),
                "-t",
                BASE_IMAGE,
                str(REPO_ROOT / "images"),
            ],
            check=True,
        )


def _build_verify_image(script, tag):
    """Build an image with a single script via Containerfile.extras."""
    build_dir = assemble_build_context(_verify_config(script), verify=True)
    try:
        subprocess.run(
            [
                "podman",
                "build",
                "-f",
                str(CONTAINERFILE_EXTRAS),
                "-t",
                tag,
                str(build_dir),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        shutil.rmtree(build_dir)


@pytest.mark.integration
@pytest.mark.parametrize("script", _get_extra_scripts(), ids=_script_ids())
def test_verify_mode(script):
    """Build image with script in verify mode via Containerfile.extras."""
    tag = f"yolo-verify-{script.stem}"
    try:
        _build_verify_image(script, tag)
    except subprocess.CalledProcessError as e:
        pytest.fail(f"{script.name} verify failed:\n{e.stdout}\n{e.stderr}")
    finally:
        subprocess.run(["podman", "rmi", tag], capture_output=True)


@pytest.mark.integration
@pytest.mark.parametrize("script", _get_extra_scripts(), ids=_script_ids())
def test_idempotent(script):
    """Build image with script, then build again on top — should succeed."""
    tag1 = f"yolo-idem1-{script.stem}"
    tag2 = f"yolo-idem2-{script.stem}"
    try:
        _build_verify_image(script, tag1)

        # Build again on top of the first image
        build_dir = assemble_build_context(_verify_config(script), verify=True)
        try:
            result = subprocess.run(
                [
                    "podman",
                    "build",
                    "--build-arg",
                    f"BASE_IMAGE={tag1}",
                    "-f",
                    str(CONTAINERFILE_EXTRAS),
                    "-t",
                    tag2,
                    str(build_dir),
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, (
                f"{script.name} not idempotent:\n{result.stdout}\n{result.stderr}"
            )
        finally:
            shutil.rmtree(build_dir)
    finally:
        subprocess.run(["podman", "rmi", tag1, tag2], capture_output=True)
