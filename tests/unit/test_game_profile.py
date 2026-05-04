"""Profile gier — ładowanie YAML i indeks."""

from __future__ import annotations

from pathlib import Path

import pytest

import yaml

from backend.config.schema import ConfigSchema
from backend.services.game_profile import (
    build_game_profile_index,
    load_profiles_from_directory,
)


def test_build_index_contains_known_game(tmp_path: Path):
    cfg = ConfigSchema()
    idx = build_game_profile_index(tmp_path, cfg)
    assert "stellaris" in idx
    assert idx["stellaris"].name == "Stellaris"
    assert "stellaris.exe" in idx["stellaris"].process_names


def test_load_yaml_overrides(tmp_path: Path):
    d = tmp_path / "game_profiles"
    d.mkdir()
    (d / "custom.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "custom",
                "name": "Custom Game",
                "process_names": ["custom.exe"],
                "context_prompt": "RTS test.",
            }
        ),
        encoding="utf-8",
    )
    loaded = load_profiles_from_directory(d)
    assert "custom" in loaded
    assert loaded["custom"].context_prompt == "RTS test."


def test_inline_config_merges(tmp_path: Path):
    cfg = ConfigSchema()
    cfg.game_profiles = {
        "inline_poe": {
            "name": "PoE Inline",
            "process_names": ["pathofexile2.exe"],
            "context_prompt": "loot",
        }
    }
    idx = build_game_profile_index(tmp_path, cfg)
    assert "inline_poe" in idx
    assert idx["inline_poe"].context_prompt == "loot"
