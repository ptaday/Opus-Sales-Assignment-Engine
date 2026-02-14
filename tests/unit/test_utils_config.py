"""Unit tests for config loading (using temp config files)."""
import pytest
from pathlib import Path
import sys
import importlib

# Import after we may patch; we'll reload for tests that patch CONFIG_DIR
from src.utils import config as config_module


class TestParseKeyValuePairs:
    def test_parses_key_number(self):
        out = config_module._parse_key_value_pairs("New:5, Working:4")
        assert out.get("New") == 5
        assert out.get("Working") == 4

    def test_parses_float(self):
        out = config_module._parse_key_value_pairs("Ratio:1.5")
        assert out.get("Ratio") == 1.5

    def test_empty_or_invalid_skipped(self):
        out = config_module._parse_key_value_pairs("A:1, B:xyz, C:2")
        assert out.get("A") == 1
        assert out.get("C") == 2


class TestParseAttributeMapping:
    def test_parses_key_slug(self):
        out = config_module._parse_attribute_mapping("company_name:company_name, owner:owner_6")
        assert out == {"company_name": "company_name", "owner": "owner_6"}

    def test_empty_string_returns_empty_dict(self):
        assert config_module._parse_attribute_mapping("") == {}


class TestResolvePath:
    def test_empty_returns_out_under_repo_root(self):
        p = config_module._resolve_path("")
        assert "out" in str(p)

    def test_relative_joins_repo_root(self):
        p = config_module._resolve_path("out/foo.csv")
        assert p.name == "foo.csv"


class TestLoadSeedConfig:
    def test_missing_file_raises(self, tmp_path, monkeypatch):
        other = tmp_path / "no_seed"
        other.mkdir()
        monkeypatch.setattr(config_module, "CONFIG_DIR", other)
        with pytest.raises(FileNotFoundError, match="Config not found"):
            config_module.load_seed_config()


class TestLoadAssignConfig:
    def test_missing_file_uses_defaults(self, monkeypatch, tmp_path):
        other = tmp_path / "no_assign"
        other.mkdir()
        monkeypatch.setattr(config_module, "CONFIG_DIR", other)
        cfg = config_module.load_assign_config()
        assert "reps" in cfg
        assert "object_type" in cfg
        assert isinstance(cfg["reps"], list)
        assert cfg["max_new_threshold"] == 2

    def test_file_overrides_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)
        (tmp_path / "assign.txt").write_text("MAX_NEW_THRESHOLD=5\nREPS=Alpha, Beta\n")
        cfg = config_module.load_assign_config()
        assert cfg["max_new_threshold"] == 5
        assert "Alpha" in cfg["reps"]
        assert "Beta" in cfg["reps"]
