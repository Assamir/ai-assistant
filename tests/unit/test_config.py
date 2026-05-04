"""Testy ConfigLoader i ConfigSchema (tydzień 1 — walidacja / YAML / env)."""

from __future__ import annotations

import pytest
import yaml

from backend.config.loader import ConfigLoader
from backend.config.schema import ConfigSchema, LogLevel


def test_defaults():
    cfg = ConfigLoader().load_config(None)
    assert cfg.log_level == LogLevel.INFO
    assert cfg.llm.api_base_url == "http://localhost:1234"
    assert cfg.stt.language == "pl"
    assert cfg.observer.observer_type == "strategy"


def test_yaml_overrides_defaults(tmp_path):
    data = {
        "log_level": "DEBUG",
        "llm": {"temperature": 0.2, "max_tokens": 256},
        "quiet_hours_start": "22:30",
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    cfg = ConfigLoader().load_config(str(path))
    assert cfg.log_level == LogLevel.DEBUG
    assert cfg.llm.temperature == pytest.approx(0.2)
    assert cfg.llm.max_tokens == 256
    assert cfg.quiet_hours_start == "22:30"


def test_yaml_nested_merge_preserves_siblings(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text(
        yaml.safe_dump({"llm": {"model_name": "custom"}}),
        encoding="utf-8",
    )
    cfg = ConfigLoader().load_config(str(path))
    assert cfg.llm.model_name == "custom"
    assert cfg.llm.api_base_url == "http://localhost:1234"


def test_missing_yaml_file_uses_defaults(tmp_path):
    cfg = ConfigLoader().load_config(str(tmp_path / "nope.yaml"))
    assert cfg.log_level == LogLevel.INFO


def test_env_overrides_top_level(monkeypatch):
    monkeypatch.setenv("ASSY_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("ASSY_QUIET_HOURS_START", "01:00")
    cfg = ConfigLoader().load_config(None)
    assert cfg.log_level == LogLevel.ERROR
    assert cfg.quiet_hours_start == "01:00"


def test_env_nested_double_underscore(monkeypatch):
    monkeypatch.setenv("ASSY_LLM__TEMPERATURE", "0.15")
    monkeypatch.setenv("ASSY_STT__CONFIDENCE_THRESHOLD", "0.5")
    cfg = ConfigLoader().load_config(None)
    assert cfg.llm.temperature == pytest.approx(0.15)
    assert cfg.stt.confidence_threshold == pytest.approx(0.5)


def test_env_bool_coercion(monkeypatch):
    monkeypatch.setenv("ASSY_MCP__ENABLED", "false")
    monkeypatch.setenv("ASSY_TTS__EMOTION_MODULATION", "1")
    cfg = ConfigLoader().load_config(None)
    assert cfg.mcp.enabled is False
    assert cfg.tts.emotion_modulation is True


def test_env_int_coercion(monkeypatch):
    monkeypatch.setenv("ASSY_AUDIO__CHUNK_SIZE", "2048")
    monkeypatch.setenv("ASSY_OBSERVER__CHECK_INTERVAL_SECONDS", "12")
    cfg = ConfigLoader().load_config(None)
    assert cfg.audio.chunk_size == 2048
    assert cfg.observer.check_interval_seconds == 12


def test_yaml_then_env_precedence(monkeypatch, tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text(yaml.safe_dump({"llm": {"temperature": 0.9}}), encoding="utf-8")
    monkeypatch.setenv("ASSY_LLM__TEMPERATURE", "0.11")
    cfg = ConfigLoader().load_config(str(path))
    assert cfg.llm.temperature == pytest.approx(0.11)


def test_invalid_log_level_in_yaml(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("log_level: NOT_A_LEVEL\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Configuration validation error"):
        ConfigLoader().load_config(str(path))


def test_commands_empty_list_default():
    cfg = ConfigSchema()
    assert cfg.commands == []


def test_load_config_invalid_yaml_syntax(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Error loading YAML"):
        ConfigLoader().load_config(str(path))


def test_env_cleared_behavior(monkeypatch):
    monkeypatch.delenv("ASSY_LOG_LEVEL", raising=False)
    cfg = ConfigLoader().load_config(None)
    assert cfg.log_level == LogLevel.INFO


def test_observer_skip_conditions_yaml(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text(
        yaml.safe_dump({"observer": {"skip_conditions": ["game_paused"]}}),
        encoding="utf-8",
    )
    cfg = ConfigLoader().load_config(str(path))
    assert cfg.observer.skip_conditions == ["game_paused"]
