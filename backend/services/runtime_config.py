"""Hot-reload: zastosowanie nowego ConfigSchema na żywo."""

from __future__ import annotations

import logging
from pathlib import Path

from backend.ai.voice_input import WakewordDetector
from backend.api.app_context import (
    AppContext,
    build_vision_pipeline,
    try_build_llm_client,
    try_build_ocr_engine,
    try_build_stt_engine,
    try_build_tts_engine,
    try_build_vlm_engine,
)
from backend.config.schema import ConfigSchema
from backend.core.command_matching import CommandMatcher
from backend.core.persona_loader import PersonaLoader
from backend.services.game_profile import build_game_profile_index

logger = logging.getLogger(__name__)


async def apply_reload_configuration(ctx: AppContext, new_cfg: ConfigSchema) -> None:
    """Aktualizuje kontekst aplikacji po zmianie YAML (bez restartu procesu)."""
    old_provider = getattr(ctx, "_last_llm_provider", None) or ctx.config.llm.provider
    ctx.config = new_cfg
    ctx.prompt_builder.max_context_tokens = new_cfg.ai_runtime.max_context_tokens

    root = Path(new_cfg.general.content_root).expanduser()
    personas_dir = root / "personas"
    personas_dir.mkdir(parents=True, exist_ok=True)
    pl = PersonaLoader(personas_dir)

    profiles = build_game_profile_index(root, new_cfg)
    ctx.game_profiles = profiles
    if ctx.game_observer is not None:
        ctx.game_observer.set_profiles(profiles)

    matcher = CommandMatcher(fuzzy=new_cfg.ai_runtime.command_match_fuzzy)
    ctx.command_matcher = matcher
    ctx.persona_loader = pl

    if ctx.game_observer is not None:
        ctx.game_observer.update_observer_config(new_cfg.observer)

    # LLM provider: hot-reload albo pełna podmiana klienta gdy provider się zmienił
    new_provider = new_cfg.llm.provider
    new_lm_client = None
    if new_provider != old_provider:
        try:
            close = getattr(ctx.llm_client, "aclose", None)
            if close is not None:
                await close()
        except Exception:
            logger.warning("aclose() previous LLM client failed", exc_info=True)
        try:
            new_lm_client, new_mgr = try_build_llm_client(
                new_cfg,
                content_root=root,
                websocket_manager=ctx.websocket_manager,
                model_manager=ctx.llm_model_manager,
            )
            ctx.llm_client = new_lm_client
            ctx.llm_model_manager = new_mgr
            for sid in ctx.websocket_manager.iter_session_ids():
                try:
                    await ctx.websocket_manager.send_to_session(
                        sid,
                        "llm_provider_changed",
                        {"provider": new_provider, "model_name": new_cfg.llm.model_name},
                    )
                except Exception:
                    pass
        except Exception as exc:
            logger.warning("Build LLM client for new provider=%s failed: %s", new_provider, exc)
    else:
        apply = getattr(ctx.llm_client, "apply_llm_config", None)
        if apply is not None:
            await apply(new_cfg.llm)
    ctx._last_llm_provider = new_provider  # type: ignore[attr-defined]

    ctx.orchestrator.apply_configuration(
        new_cfg,
        command_matcher=matcher,
        persona_loader=pl,
        lm_client=new_lm_client,
    )

    ctx.stt_engine = try_build_stt_engine(new_cfg)
    ctx.tts_engine = try_build_tts_engine(new_cfg)
    ctx.vlm_engine = try_build_vlm_engine(new_cfg)
    ctx.ocr_engine = try_build_ocr_engine(new_cfg)
    ctx.vision_pipeline = build_vision_pipeline(new_cfg, ctx.vlm_engine, ctx.ocr_engine)

    ctx.wakeword_detector = WakewordDetector(
        enabled=new_cfg.audio.wakeword_enabled,
        wakeword_models=list(new_cfg.audio.wakeword_models),
        threshold=new_cfg.audio.wakeword_threshold,
    )

    ui_payload = new_cfg.ui.model_dump(mode="json")
    for sid in ctx.websocket_manager.iter_session_ids():
        try:
            await ctx.websocket_manager.send_to_session(sid, "ui_config_changed", ui_payload)
        except Exception:
            logger.debug("ui_config_changed emit failed for sid=%s", sid, exc_info=True)

    logger.info("Runtime configuration applied (hot-reload)")


__all__ = ["apply_reload_configuration"]
