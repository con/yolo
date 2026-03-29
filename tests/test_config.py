"""Tests for yolo config loading and merging."""

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from yolo.config import _Replace, _merge, _config_paths, load_config


def _write_yaml(path: Path, data: dict):
    """Dump a dict to a YAML file, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    YAML().dump(data, path)


@pytest.fixture(autouse=True)
def _no_defaults(monkeypatch, tmp_path):
    """Point DEFAULTS_CONFIG at a nonexistent file so builtin defaults don't interfere."""
    monkeypatch.setattr("yolo.config.DEFAULTS_CONFIG", tmp_path / "no-defaults.yaml")


# ── _merge ──────────────────────────────────────────────────────


class TestMerge:
    def test_scalars_override(self):
        assert _merge({"a": 1}, {"a": 2}) == {"a": 2}

    def test_new_keys_added(self):
        assert _merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_lists_append(self):
        assert _merge({"x": [1, 2]}, {"x": [3]}) == {"x": [1, 2, 3]}

    def test_dicts_recurse(self):
        base = {"d": {"a": 1, "b": 2}}
        override = {"d": {"b": 3, "c": 4}}
        assert _merge(base, override) == {"d": {"a": 1, "b": 3, "c": 4}}

    def test_type_mismatch_override_wins(self):
        assert _merge({"a": [1, 2]}, {"a": "replaced"}) == {"a": "replaced"}

    def test_empty_base(self):
        assert _merge({}, {"a": 1}) == {"a": 1}

    def test_empty_override(self):
        assert _merge({"a": 1}, {}) == {"a": 1}

    def test_replace_tag_overrides_list(self):
        base = {"x": [1, 2, 3]}
        override = {"x": _Replace([4, 5])}
        assert _merge(base, override) == {"x": [4, 5]}

    def test_replace_on_new_key(self):
        assert _merge({}, {"x": _Replace([1])}) == {"x": [1]}


# ── _config_paths ──────────────────────────────────────────────


class TestConfigPaths:
    def test_includes_etc(self):
        paths = _config_paths()
        assert Path("/etc/yolo/config.yaml") in paths

    def test_xdg_default(self, monkeypatch):
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        paths = _config_paths()
        expected = Path.home() / ".config" / "yolo" / "config.yaml"
        assert expected in paths

    def test_xdg_override(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        paths = _config_paths()
        assert tmp_path / "yolo" / "config.yaml" in paths

    def test_project_config(self):
        paths = _config_paths()
        expected = Path.cwd() / ".yolo" / "config.yaml"
        assert expected in paths

    def test_precedence_order(self, monkeypatch):
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        paths = _config_paths()
        # etc < xdg < project < git
        assert paths[0] == Path("/etc/yolo/config.yaml")
        assert paths[1] == Path.home() / ".config" / "yolo" / "config.yaml"
        assert paths[2] == Path.cwd() / ".yolo" / "config.yaml"


# ── load_config ────────────────────────────────────────────────


class TestLoadConfig:
    def test_empty_when_no_files(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no-xdg"))
        config = load_config()
        assert config == {}

    def test_loads_single_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        _write_yaml(
            tmp_path / ".yolo" / "config.yaml",
            {
                "nvidia": True,
                "container-extras": ["zsh"],
            },
        )
        config = load_config()
        assert config["nvidia"] is True
        assert config["container-extras"] == ["zsh"]

    def test_merges_layers(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        xdg = tmp_path / "xdg"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        _write_yaml(
            xdg / "yolo" / "config.yaml",
            {
                "nvidia": False,
                "container-extras": ["zsh"],
            },
        )

        _write_yaml(
            tmp_path / ".yolo" / "config.yaml",
            {
                "nvidia": True,
                "container-extras": ["python"],
            },
        )

        config = load_config()
        assert config["nvidia"] is True
        assert config["container-extras"] == ["zsh", "python"]

    def test_git_yolo_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no-xdg"))

        (tmp_path / ".git").mkdir()
        _write_yaml(
            tmp_path / ".git" / "yolo" / "config.yaml",
            {
                "worktree": "bind",
            },
        )

        config = load_config()
        assert config["worktree"] == "bind"

    def test_git_overrides_project(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no-xdg"))

        _write_yaml(
            tmp_path / ".yolo" / "config.yaml",
            {
                "worktree": "ask",
            },
        )

        (tmp_path / ".git").mkdir()
        _write_yaml(
            tmp_path / ".git" / "yolo" / "config.yaml",
            {
                "worktree": "skip",
            },
        )

        config = load_config()
        assert config["worktree"] == "skip"

    def test_replace_tag_in_yaml(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        xdg = tmp_path / "xdg"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        _write_yaml(
            xdg / "yolo" / "config.yaml",
            {"extras": ["zsh", "fzf", "python"]},
        )

        # Write raw YAML with !replace tag (can't use _write_yaml for tags)
        project_cfg = tmp_path / ".yolo" / "config.yaml"
        project_cfg.parent.mkdir(parents=True, exist_ok=True)
        project_cfg.write_text("extras: !replace\n  - datalad\n")

        config = load_config()
        assert config["extras"] == ["datalad"]
