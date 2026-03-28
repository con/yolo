"""Tests for yolo config loading and merging."""

import os
from pathlib import Path

import pytest
import yaml

from yolo.config import _merge, _config_paths, _find_git_dir, load_config


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
        config_dir = tmp_path / ".yolo"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(yaml.dump({
            "nvidia": True,
            "container-extras": ["zsh"],
        }))
        config = load_config()
        assert config["nvidia"] is True
        assert config["container-extras"] == ["zsh"]

    def test_merges_layers(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        # User config
        xdg = tmp_path / "xdg"
        (xdg / "yolo").mkdir(parents=True)
        (xdg / "yolo" / "config.yaml").write_text(yaml.dump({
            "nvidia": False,
            "container-extras": ["zsh"],
        }))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))

        # Project config
        (tmp_path / ".yolo").mkdir()
        (tmp_path / ".yolo" / "config.yaml").write_text(yaml.dump({
            "nvidia": True,
            "container-extras": ["python"],
        }))

        config = load_config()
        # Scalar: project overrides user
        assert config["nvidia"] is True
        # List: appended
        assert config["container-extras"] == ["zsh", "python"]

    def test_git_yolo_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no-xdg"))

        # Create a git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        config_dir = git_dir / "yolo"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(yaml.dump({
            "worktree": "bind",
        }))

        config = load_config()
        assert config["worktree"] == "bind"

    def test_git_overrides_project(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no-xdg"))

        # Project config (.yolo/)
        (tmp_path / ".yolo").mkdir()
        (tmp_path / ".yolo" / "config.yaml").write_text(yaml.dump({
            "worktree": "ask",
        }))

        # Git config (.git/yolo/) — higher precedence
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        config_dir = git_dir / "yolo"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text(yaml.dump({
            "worktree": "skip",
        }))

        config = load_config()
        assert config["worktree"] == "skip"
