"""Tests for yolo CLI commands."""

from unittest.mock import patch

from click.testing import CliRunner

from yolo.cli import main


class TestClip:
    def test_clip_no_content(self, tmp_path):
        with patch("yolo.cli.Path.home", return_value=tmp_path):
            runner = CliRunner()
            result = runner.invoke(main, ["clip"])
            assert result.exit_code != 0
            assert "Nothing to clip" in result.output

    def test_clip_copies_content(self, tmp_path):
        clip_dir = tmp_path / ".local" / "share" / "yolo" / "clip"
        clip_dir.mkdir(parents=True)
        (clip_dir / "content").write_text("hello world")

        with (
            patch("yolo.cli.Path.home", return_value=tmp_path),
            patch("yolo.cli.subprocess.run") as mock_run,
            patch("yolo.cli.load_config", return_value={}),
        ):
            runner = CliRunner()
            result = runner.invoke(main, ["clip"])
            assert result.exit_code == 0
            assert "11 chars" in result.output
            mock_run.assert_called_once()
            assert mock_run.call_args.kwargs["input"] == "hello world"

    def test_clip_custom_command(self, tmp_path):
        clip_dir = tmp_path / ".local" / "share" / "yolo" / "clip"
        clip_dir.mkdir(parents=True)
        (clip_dir / "content").write_text("test")

        with (
            patch("yolo.cli.Path.home", return_value=tmp_path),
            patch("yolo.cli.subprocess.run") as mock_run,
            patch(
                "yolo.cli.load_config",
                return_value={"host_clipboard_command": "wl-copy"},
            ),
        ):
            runner = CliRunner()
            result = runner.invoke(main, ["clip"])
            assert result.exit_code == 0
            assert mock_run.call_args[0][0] == ["wl-copy"]
