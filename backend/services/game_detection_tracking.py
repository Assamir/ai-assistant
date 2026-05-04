"""SQLite `game_detections` — zapis przy start/stop obserwatora i przy `game_detected`."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from backend.api.app_context import AppContext
from backend.db.repositories import GameDetectionRepository

_logger = logging.getLogger(__name__)


async def record_game_detection_on_game_emit(ctx: AppContext, payload: Mapping[str, Any]) -> None:
    """Wywoływane z `make_game_emitter` po aktualizacji stanu dla zdarzenia `game_detected`."""
    if not ctx.orchestrator.state.get("observer_active"):
        return
    db_ids = list(ctx.db_session_by_ws.values())
    if not db_ids:
        return
    try:
        repo = GameDetectionRepository(ctx.db_path)
        method = "manual" if ctx.orchestrator.state.get("manual_game_profile_lock") else "process"
        active = payload.get("active") is True
        game_raw = payload.get("game")
        game_label = (
            game_raw.strip()
            if isinstance(game_raw, str) and game_raw.strip()
            else None
        )
        for chat_sid in db_ids:
            await repo.close_open_for_chat_session(chat_sid)
        if active and game_label:
            for chat_sid in db_ids:
                await repo.start_detection(
                    chat_sid,
                    game_label,
                    detection_method=method,
                )
    except Exception as exc:
        _logger.debug("game_detections (game_emit) skipped: %s", exc)


async def sync_game_detections_on_observer_command(ctx: AppContext, event_name: str) -> None:
    """`observer_start` / `observer_stop` z komend frontendu."""
    db_ids = list(ctx.db_session_by_ws.values())
    if not db_ids:
        return
    try:
        repo = GameDetectionRepository(ctx.db_path)
        if event_name == "observer_stop":
            for chat_sid in db_ids:
                await repo.close_open_for_chat_session(chat_sid)
            return
        if event_name != "observer_start":
            return
        method = "manual" if ctx.orchestrator.state.get("manual_game_profile_lock") else "process"
        cur = ctx.orchestrator.state.get("current_game")
        game_label = cur.strip() if isinstance(cur, str) and cur.strip() else "unknown"
        for chat_sid in db_ids:
            await repo.close_open_for_chat_session(chat_sid)
            await repo.start_detection(
                chat_sid,
                game_label,
                detection_method=method,
            )
    except Exception as exc:
        _logger.debug("game_detections (observer_command) skipped: %s", exc)


__all__ = [
    "record_game_detection_on_game_emit",
    "sync_game_detections_on_observer_command",
]
