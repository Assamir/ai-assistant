"""Hot-reload: zastosowanie nowego ConfigSchema na żywo."""

from __future__ import annotations

import logging
from pathlib import Path

from backend.ai.voice_input import WakewordDetector
from backend.api.app_context import (
    AppContext,
    build_vision_pipeline,
    try_build_ocr_engine,
    try_build_stt_engine,
    try_build_tts_engine,
    try_build_vlm_engine,
)
from backend.config.schema import ConfigSchema
from backend.core.command_matching import CommandMatcher
from backend.core.persona_loader import PersonaLoader

logger = logging.getLogger(__name__)


async def apply_reload_configuration(ctx: AppContext, new_cfg: ConfigSchema) -> None:
    """Aktualizuje kontekst aplikacji po zmianie YAML (bez restartu procesu)."""
    ctx.config = new_cfg
    ctx.prompt_builder.max_context_tokens = new_cfg.ai_runtime.max_context_tokens

    root = Path(new_cfg.general.content_root).expanduser()
    personas_dir = root / "personas"
    personas_dir.mkdir(parents=True, exist_ok=True)
    pl = PersonaLoader(personas_dir)

    matcher = CommandMatcher(fuzzy=new_cfg.ai_runtime.command_match_fuzzy)
    ctx.command_matcher = matcher
    ctx.persona_loader = pl
    ctx.orchestrator.apply_configuration(
        new_cfg,
        command_matcher=matcher,
        persona_loader=pl,
    )

    if ctx.game_observer is not None:
        ctx.game_observer.update_observer_config(new_cfg.observer)

    await ctx.llm_client.apply_llm_config(new_cfg.llm)

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

    logger.info("Runtime configuration applied (hot-reload)")


__all__ = ["apply_reload_configuration"]
