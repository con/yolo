"""Tests for yolo launcher: command assembly."""

from pathlib import Path
from unittest.mock import patch

import pytest

from yolo.launcher import (
    _build_volume_args,
    _detect_worktree,
    _expand_volume,
    _nvidia_args,
    _worktree_volume,
    run,
)


@pytest.fixture(autouse=True)
def _mock_image_tag():
    with patch("yolo.launcher.image_tag", return_value="yolo-test-default"):
        yield


class TestExpandVolume:
    def test_shorthand(self):
        result = _expand_volume("~/projects")
        home = str(Path.home())
        assert result == f"{home}/projects:{home}/projects:z"

    def test_shorthand_with_options(self):
        result = _expand_volume("~/data::ro")
        home = str(Path.home())
        assert result == f"{home}/data:{home}/data:ro"

    def test_partial(self):
        assert _expand_volume("/host:/container") == "/host:/container:z"

    def test_full_passthrough(self):
        assert _expand_volume("/host:/container:ro,z") == "/host:/container:ro,z"

    def test_absolute_shorthand(self):
        assert _expand_volume("/data") == "/data:/data:z"


class TestBuildVolumeArgs:
    def test_empty(self):
        assert _build_volume_args([]) == []

    def test_single(self):
        assert _build_volume_args(["/a:/b:z"]) == ["-v", "/a:/b:z"]

    def test_multiple(self):
        result = _build_volume_args(["/a:/b:z", "/c:/d:ro,z"])
        assert result == ["-v", "/a:/b:z", "-v", "/c:/d:ro,z"]


def _sub_run_image_exists(cmd, **kw):
    """Mock subprocess.run: return success for 'podman image exists'."""
    if cmd[:2] == ["podman", "image"]:
        return type("R", (), {"returncode": 0})()


class TestRun:
    @patch("yolo.launcher.subprocess.run", side_effect=_sub_run_image_exists)
    @patch("yolo.launcher.load_config", return_value={})
    def test_basic_command(self, mock_config, mock_run):
        run()
        cmd = mock_run.call_args[0][0]
        assert "podman" == cmd[0]
        assert "run" == cmd[1]
        assert "--userns=keep-id" in cmd
        assert "claude" in cmd
        assert "--dangerously-skip-permissions" in cmd
        assert "yolo-test-default" in cmd

    @patch("yolo.launcher.subprocess.run", side_effect=_sub_run_image_exists)
    @patch("yolo.launcher.load_config", return_value={})
    def test_claude_args_passed(self, mock_config, mock_run):
        run(claude_args=["--resume"])
        cmd = mock_run.call_args[0][0]
        assert "--resume" in cmd
        idx = cmd.index("--dangerously-skip-permissions")
        assert cmd[idx + 1] == "--resume"

    @patch("yolo.launcher.subprocess.run", side_effect=_sub_run_image_exists)
    @patch("yolo.launcher.load_config", return_value={})
    def test_extra_volumes(self, mock_config, mock_run):
        run(extra_volumes=["/data:/data:z"])
        cmd = mock_run.call_args[0][0]
        assert "-v" in cmd
        assert "/data:/data:z" in cmd

    @patch("yolo.launcher.subprocess.run", side_effect=_sub_run_image_exists)
    @patch(
        "yolo.launcher.load_config",
        return_value={"volumes": ["/cfg:/cfg:ro,z"]},
    )
    def test_config_volumes(self, mock_config, mock_run):
        run()
        cmd = mock_run.call_args[0][0]
        assert "/cfg:/cfg:ro,z" in cmd

    @patch("yolo.launcher.subprocess.run", side_effect=_sub_run_image_exists)
    @patch(
        "yolo.launcher.load_config",
        return_value={"volumes": ["/cfg:/cfg:z"]},
    )
    def test_config_and_extra_volumes(self, mock_config, mock_run):
        run(extra_volumes=["/cli:/cli:z"])
        cmd = mock_run.call_args[0][0]
        assert "/cfg:/cfg:z" in cmd
        assert "/cli:/cli:z" in cmd

    @patch("yolo.launcher.subprocess.run", side_effect=_sub_run_image_exists)
    @patch("yolo.launcher.load_config", return_value={})
    def test_custom_entrypoint(self, mock_config, mock_run):
        run(entrypoint="bash")
        cmd = mock_run.call_args[0][0]
        assert "bash" in cmd
        assert "claude" not in cmd
        assert "--dangerously-skip-permissions" not in cmd

    @patch("yolo.launcher.subprocess.run", side_effect=_sub_run_image_exists)
    @patch("yolo.launcher.load_config", return_value={})
    def test_custom_entrypoint_with_args(self, mock_config, mock_run):
        run(entrypoint="bash", claude_args=["-c", "echo hi"])
        cmd = mock_run.call_args[0][0]
        idx = cmd.index("bash")
        assert cmd[idx + 1 : idx + 3] == ["-c", "echo hi"]

    @patch("yolo.launcher.image_tag")
    @patch("yolo.launcher.subprocess.run", side_effect=_sub_run_image_exists)
    @patch("yolo.launcher.load_config", return_value={})
    def test_image_name_passed(self, mock_config, mock_run, mock_tag):
        mock_tag.return_value = "yolo-myproject-heavy"
        run(image_name="heavy")
        mock_tag.assert_called_with("heavy")
        cmd = mock_run.call_args[0][0]
        assert "yolo-myproject-heavy" in cmd

    @patch("yolo.launcher.build")
    @patch("yolo.launcher.subprocess.run")
    @patch("yolo.launcher.load_config", return_value={"images": [{"name": "default"}]})
    def test_auto_build_when_image_missing(self, mock_config, mock_run, mock_build):
        mock_run.return_value = type("R", (), {"returncode": 1})()
        run()
        mock_build.assert_called_once_with([{"name": "default"}], only=None)

    @patch("yolo.launcher.build")
    @patch("yolo.launcher.subprocess.run", side_effect=_sub_run_image_exists)
    @patch("yolo.launcher.load_config", return_value={})
    def test_no_build_when_image_exists(self, mock_config, mock_run, mock_build):
        run()
        mock_build.assert_not_called()


class TestNvidiaArgs:
    def test_disabled(self):
        assert _nvidia_args(False) == []

    def test_enabled(self):
        result = _nvidia_args(True)
        assert "--device" in result
        assert "nvidia.com/gpu=all" in result
        assert "--security-opt" in result
        assert "label=disable" in result


class TestDetectWorktree:
    def test_not_a_worktree(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        assert _detect_worktree() is None

    def test_no_git_at_all(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert _detect_worktree() is None

    def test_detects_worktree(self, tmp_path, monkeypatch):
        # Set up fake worktree structure
        original = tmp_path / "original"
        original.mkdir()
        git_dir = original / ".git"
        git_dir.mkdir()
        worktrees = git_dir / "worktrees" / "wt1"
        worktrees.mkdir(parents=True)

        wt = tmp_path / "worktree1"
        wt.mkdir()
        (wt / ".git").write_text(f"gitdir: {worktrees}")
        monkeypatch.chdir(wt)

        assert _detect_worktree() == original


class TestWorktreeVolume:
    def test_skip_no_worktree(self):
        with patch("yolo.launcher._detect_worktree", return_value=None):
            assert _worktree_volume("ask") == []

    def test_bind_mounts(self):
        with patch(
            "yolo.launcher._detect_worktree",
            return_value=Path("/repo"),
        ):
            result = _worktree_volume("bind")
            assert result == ["-v", "/repo:/repo:z"]

    def test_skip_mode(self):
        with patch(
            "yolo.launcher._detect_worktree",
            return_value=Path("/repo"),
        ):
            assert _worktree_volume("skip") == []

    def test_error_mode(self):
        with patch(
            "yolo.launcher._detect_worktree",
            return_value=Path("/repo"),
        ):
            with pytest.raises(SystemExit):
                _worktree_volume("error")
