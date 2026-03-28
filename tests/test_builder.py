"""Tests for yolo builder: extras parsing, script resolution, build context assembly."""

import shutil
from pathlib import Path

import pytest

from yolo.builder import _parse_extra, _resolve_script, assemble_build_context


# ── _parse_extra ───────────────────────────────────────────────


class TestParseExtra:
    def test_string_entry(self):
        assert _parse_extra("datalad") == ("datalad", {})

    def test_name_only_dict(self):
        assert _parse_extra({"name": "datalad"}) == ("datalad", {})

    def test_dict_with_string_param(self):
        name, env = _parse_extra({"name": "python", "version": "3.12"})
        assert name == "python"
        assert env == {"YOLO_PYTHON_VERSION": "3.12"}

    def test_dict_with_list_param(self):
        name, env = _parse_extra({"name": "apt", "packages": ["zsh", "fzf"]})
        assert name == "apt"
        assert env == {"YOLO_APT_PACKAGES": "zsh fzf"}

    def test_multiple_params(self):
        name, env = _parse_extra({"name": "foo", "version": "1.0", "flavor": "slim"})
        assert name == "foo"
        assert env == {"YOLO_FOO_VERSION": "1.0", "YOLO_FOO_FLAVOR": "slim"}

    def test_missing_name_raises(self):
        with pytest.raises(ValueError, match="must have 'name'"):
            _parse_extra({"packages": ["zsh"]})

    def test_non_dict_non_string_raises(self):
        with pytest.raises(ValueError):
            _parse_extra(42)


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


# ── assemble_build_context ─────────────────────────────────────


class TestAssembleBuildContext:
    def _make_extras_dir(self, tmp_path, scripts: dict[str, str]) -> Path:
        extras_dir = tmp_path / "extras"
        extras_dir.mkdir()
        for name, content in scripts.items():
            (extras_dir / f"{name}.sh").write_text(content)
        return extras_dir

    def test_creates_run_sh_with_env_vars(self, tmp_path, monkeypatch):
        extras_dir = self._make_extras_dir(tmp_path, {"apt": "#!/bin/bash"})
        monkeypatch.setattr("yolo.builder._extras_search_path", lambda: [extras_dir])

        build_dir = assemble_build_context([{"name": "apt", "packages": ["zsh", "fzf"]}])
        try:
            content = (build_dir / "build" / "run.sh").read_text()
            assert 'YOLO_APT_PACKAGES="zsh fzf"' in content
            assert "apt.sh" in content
        finally:
            shutil.rmtree(build_dir)

    def test_no_env_vars_for_bare_name(self, tmp_path, monkeypatch):
        extras_dir = self._make_extras_dir(tmp_path, {"datalad": "#!/bin/bash"})
        monkeypatch.setattr("yolo.builder._extras_search_path", lambda: [extras_dir])

        build_dir = assemble_build_context([{"name": "datalad"}])
        try:
            content = (build_dir / "build" / "run.sh").read_text()
            assert "bash /tmp/yolo-build/scripts/datalad.sh" in content
            assert "YOLO_" not in content
        finally:
            shutil.rmtree(build_dir)

    def test_copies_scripts(self, tmp_path, monkeypatch):
        extras_dir = self._make_extras_dir(tmp_path, {
            "apt": "#!/bin/bash",
            "python": "#!/bin/bash",
        })
        monkeypatch.setattr("yolo.builder._extras_search_path", lambda: [extras_dir])

        config = [
            {"name": "apt", "packages": ["vim"]},
            {"name": "python", "version": "3.12"},
        ]
        build_dir = assemble_build_context(config)
        try:
            scripts_dir = build_dir / "build" / "scripts"
            assert (scripts_dir / "apt.sh").exists()
            assert (scripts_dir / "python.sh").exists()
        finally:
            shutil.rmtree(build_dir)

    def test_raises_on_missing_script(self, tmp_path, monkeypatch):
        monkeypatch.setattr("yolo.builder._extras_search_path", lambda: [tmp_path])

        with pytest.raises(FileNotFoundError, match="nope"):
            assemble_build_context([{"name": "nope"}])

    def test_string_entry(self, tmp_path, monkeypatch):
        extras_dir = self._make_extras_dir(tmp_path, {"datalad": "#!/bin/bash"})
        monkeypatch.setattr("yolo.builder._extras_search_path", lambda: [extras_dir])

        build_dir = assemble_build_context(["datalad"])
        try:
            content = (build_dir / "build" / "run.sh").read_text()
            assert "datalad.sh" in content
        finally:
            shutil.rmtree(build_dir)
