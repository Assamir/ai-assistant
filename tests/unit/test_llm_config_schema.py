"""Sprawdza wsteczną kompatybilność i nowe pola LLMConfig (provider + local + openrouter)."""

from __future__ import annotations

from backend.config.schema import ConfigSchema, LLMConfig, LocalLLMConfig, OpenRouterLLMConfig


def test_legacy_llm_config_validates_without_new_fields():
    """Stary YAML (tylko płaskie api_base_url + model_name) musi się walidować."""
    cfg = LLMConfig.model_validate({
        "api_base_url": "http://localhost:1234",
        "model_name": "qwen2.5-14b-instruct",
        "temperature": 0.3,
    })
    assert cfg.provider == "lm_studio"
    assert cfg.api_base_url == "http://localhost:1234"
    assert cfg.model_name == "qwen2.5-14b-instruct"
    assert isinstance(cfg.local, LocalLLMConfig)
    assert isinstance(cfg.openrouter, OpenRouterLLMConfig)


def test_provider_local_with_nested_config():
    cfg = LLMConfig.model_validate({
        "provider": "local",
        "local": {
            "model_id": "unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF",
            "preferred_quant": "Q5_K_M",
            "n_gpu_layers": 30,
            "n_ctx": 16384,
        },
    })
    assert cfg.provider == "local"
    assert cfg.local.model_id == "unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF"
    assert cfg.local.preferred_quant == "Q5_K_M"
    assert cfg.local.n_gpu_layers == 30
    assert cfg.local.n_ctx == 16384


def test_provider_openrouter_with_api_key():
    cfg = LLMConfig.model_validate({
        "provider": "openrouter",
        "openrouter": {
            "api_key": "sk-or-test",
            "model_name": "anthropic/claude-sonnet-4.6",
        },
    })
    assert cfg.provider == "openrouter"
    assert cfg.openrouter.api_key == "sk-or-test"
    assert cfg.openrouter.model_name == "anthropic/claude-sonnet-4.6"
    assert cfg.openrouter.api_base_url == "https://openrouter.ai/api/v1"


def test_config_schema_defaults_to_lm_studio():
    cfg = ConfigSchema()
    assert cfg.llm.provider == "lm_studio"
    assert cfg.llm.local.auto_download is True
    assert cfg.llm.local.model_id.endswith("-GGUF")


def test_provider_enum_rejects_unknown():
    """Provider musi być jednym z dozwolonych."""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LLMConfig.model_validate({"provider": "ollama"})
