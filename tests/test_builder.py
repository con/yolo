"""Tests for yolo builder: extras parsing, script resolution, build context assembly."""

from pathlib import Path

import pytest

from yolo.builder import _parse_extras, _resolve_script, _collect_apt_fallbacks, assemble_build_context


# ── _parse_extras ──────────────────────────────────────────────


class TestParseExtras:
    def test_bare_name(self):
        assert _parse_extras(["datalad"]) == [("datalad", [])]

    def test_prefixed_name(self):
        assert _parse_extras(["apt:imagemagick"]) == [("apt", ["imagemagick"])]

    def test_dict_with_string_arg(self):
        assert _parse_extras([{"python": "3.12"}]) == [("python", ["3.12"])]

    def test_dict_with_list_arg(self):
        assert _parse_extras([{"apt": ["zsh", "fzf"]}]) == [("apt", ["zsh", "fzf"])]

    def test_mixed(self):
        config = ["datalad", "apt:vim", {"python": "3.12"}]
        assert _parse_extras(config) == [
            ("datalad", []),
            ("apt", ["vim"]),
            ("python", ["3.12"]),
        ]

    def test_empty(self):
        assert _parse_extras([]) == []


# ── _resolve_script ────────────────────────────────────────────


class TestResolveScript:
    def test_finds_script(self, tmp_path):
        script = tmp_path / "datalad.sh"
        script.write_text("#!/bin/bash\necho hi")
        assert _resolve_script("datalad", [tmp_path]) == script

    def test_returns_none_when_missing(self, tmp_path):
        assert _resolve_script("nope", [tmp_path]) is None

    def test_later_path_wins(self, tmp_path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "tool.sh").write_text("old")
        (dir_b / "tool.sh").write_text("new")
        result = _resolve_script("tool", [dir_a, dir_b])
        assert result == dir_b / "tool.sh"


# ── _collect_apt_fallbacks ─────────────────────────────────────


class TestCollectAptFallbacks:
    def test_bare_name_without_script_becomes_apt(self, tmp_path):
        parsed = [("zsh", []), ("fzf", [])]
        result = _collect_apt_fallbacks(parsed, [tmp_path])
        assert result == [("apt", ["zsh", "fzf"])]

    def test_bare_name_with_script_stays(self, tmp_path):
        (tmp_path / "datalad.sh").write_text("#!/bin/bash")
        parsed = [("datalad", [])]
        result = _collect_apt_fallbacks(parsed, [tmp_path])
        assert result == [("datalad", [])]

    def test_prefixed_stays(self, tmp_path):
        parsed = [("apt", ["vim"])]
        result = _collect_apt_fallbacks(parsed, [tmp_path])
        assert result == [("apt", ["vim"])]

    def test_batches_consecutive_apt_fallbacks(self, tmp_path):
        (tmp_path / "datalad.sh").write_text("#!/bin/bash")
        parsed = [("zsh", []), ("fzf", []), ("datalad", []), ("vim", [])]
        result = _collect_apt_fallbacks(parsed, [tmp_path])
        assert result == [
            ("apt", ["zsh", "fzf"]),
            ("datalad", []),
            ("apt", ["vim"]),
        ]


# ── assemble_build_context ─────────────────────────────────────


class TestAssembleBuildContext:
    def test_creates_run_sh(self, tmp_path, monkeypatch):
        # Set up a fake extras dir with apt.sh
        extras_dir = tmp_path / "extras"
        extras_dir.mkdir()
        (extras_dir / "apt.sh").write_text("apt-get install -y \"$@\"")

        monkeypatch.setattr("yolo.builder._extras_search_path", lambda: [extras_dir])

        build_dir = assemble_build_context(["zsh", "fzf"])
        try:
            run_sh = build_dir / "build" / "run.sh"
            assert run_sh.exists()
            content = run_sh.read_text()
            assert "apt.sh zsh fzf" in content
        finally:
            import shutil
            shutil.rmtree(build_dir)

    def test_copies_scripts(self, tmp_path, monkeypatch):
        extras_dir = tmp_path / "extras"
        extras_dir.mkdir()
        (extras_dir / "apt.sh").write_text("apt-get install -y \"$@\"")
        (extras_dir / "python.sh").write_text("uv python install \"$1\"")

        monkeypatch.setattr("yolo.builder._extras_search_path", lambda: [extras_dir])

        build_dir = assemble_build_context(["apt:vim", {"python": "3.12"}])
        try:
            scripts_dir = build_dir / "build" / "scripts"
            assert (scripts_dir / "apt.sh").exists()
            assert (scripts_dir / "python.sh").exists()
        finally:
            import shutil
            shutil.rmtree(build_dir)

    def test_raises_on_missing_script(self, tmp_path, monkeypatch):
        monkeypatch.setattr("yolo.builder._extras_search_path", lambda: [tmp_path])

        with pytest.raises(FileNotFoundError, match="apt"):
            assemble_build_context(["apt:vim"])

    def test_run_sh_has_args(self, tmp_path, monkeypatch):
        extras_dir = tmp_path / "extras"
        extras_dir.mkdir()
        (extras_dir / "python.sh").write_text("uv python install \"$1\"")

        monkeypatch.setattr("yolo.builder._extras_search_path", lambda: [extras_dir])

        build_dir = assemble_build_context([{"python": "3.12"}])
        try:
            content = (build_dir / "build" / "run.sh").read_text()
            assert "python.sh 3.12" in content
        finally:
            import shutil
            shutil.rmtree(build_dir)
