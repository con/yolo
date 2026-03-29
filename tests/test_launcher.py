"""Tests for yolo launcher: command assembly."""

from unittest.mock import patch

from yolo.launcher import _build_volume_args, run


class TestBuildVolumeArgs:
    def test_empty(self):
        assert _build_volume_args([]) == []

    def test_single(self):
        assert _build_volume_args(["/a:/b:z"]) == ["-v", "/a:/b:z"]

    def test_multiple(self):
        result = _build_volume_args(["/a:/b:z", "/c:/d:ro,z"])
        assert result == ["-v", "/a:/b:z", "-v", "/c:/d:ro,z"]


class TestRun:
    @patch("yolo.launcher.subprocess.run")
    @patch("yolo.launcher.load_config", return_value={})
    def test_basic_command(self, mock_config, mock_run):
        run()
        cmd = mock_run.call_args[0][0]
        assert "podman" == cmd[0]
        assert "run" == cmd[1]
        assert "--userns=keep-id" in cmd
        assert "claude" in cmd
        assert "--dangerously-skip-permissions" in cmd

    @patch("yolo.launcher.subprocess.run")
    @patch("yolo.launcher.load_config", return_value={})
    def test_claude_args_passed(self, mock_config, mock_run):
        run(claude_args=["--resume"])
        cmd = mock_run.call_args[0][0]
        assert "--resume" in cmd
        idx = cmd.index("--dangerously-skip-permissions")
        assert cmd[idx + 1] == "--resume"

    @patch("yolo.launcher.subprocess.run")
    @patch("yolo.launcher.load_config", return_value={})
    def test_extra_volumes(self, mock_config, mock_run):
        run(extra_volumes=["/data:/data:z"])
        cmd = mock_run.call_args[0][0]
        assert "-v" in cmd
        assert "/data:/data:z" in cmd

    @patch("yolo.launcher.subprocess.run")
    @patch(
        "yolo.launcher.load_config",
        return_value={"volumes": ["/cfg:/cfg:ro,z"]},
    )
    def test_config_volumes(self, mock_config, mock_run):
        run()
        cmd = mock_run.call_args[0][0]
        assert "/cfg:/cfg:ro,z" in cmd

    @patch("yolo.launcher.subprocess.run")
    @patch(
        "yolo.launcher.load_config",
        return_value={"volumes": ["/cfg:/cfg:z"]},
    )
    def test_config_and_extra_volumes(self, mock_config, mock_run):
        run(extra_volumes=["/cli:/cli:z"])
        cmd = mock_run.call_args[0][0]
        assert "/cfg:/cfg:z" in cmd
        assert "/cli:/cli:z" in cmd

    @patch("yolo.launcher.subprocess.run")
    @patch("yolo.launcher.load_config", return_value={})
    def test_custom_entrypoint(self, mock_config, mock_run):
        run(entrypoint="bash")
        cmd = mock_run.call_args[0][0]
        assert "bash" in cmd
        assert "claude" not in cmd
        assert "--dangerously-skip-permissions" not in cmd

    @patch("yolo.launcher.subprocess.run")
    @patch("yolo.launcher.load_config", return_value={})
    def test_custom_entrypoint_with_args(self, mock_config, mock_run):
        run(entrypoint="bash", claude_args=["-c", "echo hi"])
        cmd = mock_run.call_args[0][0]
        idx = cmd.index("bash")
        assert cmd[idx + 1 : idx + 3] == ["-c", "echo hi"]
