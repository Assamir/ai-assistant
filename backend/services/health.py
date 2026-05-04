"""Agregacja stanu zdrowia komponentów dla `/api/v1/status` i `/api/v1/health`."""

from __future__ import annotations

from typing import Any, Dict

from backend.api.app_context import AppContext


def build_health_snapshot(ctx: AppContext) -> Dict[str, Any]:
    """Zwraca strukturę pod HTTP (bez sekretów)."""
    breaker = getattr(ctx.llm_client, "_breaker", None)
    cb_state = getattr(breaker, "state", None) if breaker else None
    cb_failures = int(getattr(breaker, "failure_count", 0)) if breaker else 0

    components = {
        "llm": {
            "circuit_breaker": cb_state,
            "failure_count": cb_failures,
            "api_base_url": ctx.config.llm.api_base_url,
        },
        "stt": {"available": ctx.stt_engine is not None},
        "tts": {"available": ctx.tts_engine is not None},
        "vlm": {
            "enabled_in_config": ctx.config.vlm.enabled,
            "engine_initialized": ctx.vlm_engine is not None,
        },
        "ocr": {
            "enabled_in_config": ctx.config.ocr.enabled,
            "engine_initialized": ctx.ocr_engine is not None,
        },
        "vision_pipeline": {"available": ctx.vision_pipeline is not None},
        "database": {"path": ctx.db_path},
        "observer": {
            "running": ctx.game_observer.is_running if ctx.game_observer else False,
            "check_interval_seconds": ctx.config.observer.check_interval_seconds,
            "vision_loop_running": ctx.observer_loop.is_running if ctx.observer_loop else False,
            "cycle_interval_seconds": ctx.config.observer.cycle_interval_seconds,
        },
    }

    overall = "healthy"
    if cb_state == "OPEN":
        overall = "degraded"

    return {
        "overall": overall,
        "components": components,
        "config": {
            "resolved_yaml": ctx.resolved_config_path,
            "yaml_tracked": ctx.resolved_config_path is not None,
        },
    }


__all__ = ["build_health_snapshot"]
