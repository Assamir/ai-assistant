"""Konfiguracja CORS z ENV."""

from __future__ import annotations

from backend.config.cors_settings import cors_middleware_params


def test_cors_default_wildcard_no_credentials(monkeypatch):
    monkeypatch.delenv("ASSYSTENT_CORS_ORIGINS", raising=False)
    p = cors_middleware_params()
    assert p["allow_origins"] == ["*"]
    assert p["allow_credentials"] is False


def test_cors_explicit_star_in_env(monkeypatch):
    monkeypatch.setenv("ASSYSTENT_CORS_ORIGINS", "*")
    p = cors_middleware_params()
    assert p["allow_origins"] == ["*"]
    assert p["allow_credentials"] is False


def test_cors_explicit_origins_enable_credentials(monkeypatch):
    monkeypatch.setenv(
        "ASSYSTENT_CORS_ORIGINS",
        "http://localhost:5173, http://127.0.0.1:5173",
    )
    p = cors_middleware_params()
    assert p["allow_origins"] == ["http://localhost:5173", "http://127.0.0.1:5173"]
    assert p["allow_credentials"] is True
