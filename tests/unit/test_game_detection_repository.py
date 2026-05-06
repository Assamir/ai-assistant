"""GameDetectionRepository + game_detection_tracking hooks."""

from __future__ import annotations

from types import SimpleNamespace

from backend.config.schema import ConfigSchema
from unittest.mock import AsyncMock

import pytest

from backend.api.app_context import make_game_emitter
from backend.db.repositories import GameDetectionRepository, SessionRepository
from backend.services.game_detection_tracking import (
    record_game_detection_on_game_emit,
    sync_game_detections_on_observer_command,
)


@pytest.mark.asyncio
async def test_start_and_close_roundtrip(migrated_db_path):
    sessions = SessionRepository(migrated_db_path)
    det = GameDetectionRepository(migrated_db_path)
    sid = await sessions.start_session()
    await det.start_detection(sid, "Stellaris", detection_method="process")
    rows = await det.list_for_chat_session(sid)
    assert len(rows) == 1
    assert rows[0]["ended_at"] is None
    assert rows[0]["game"] == "Stellaris"
    assert rows[0]["detection_method"] == "process"

    await det.close_open_for_chat_session(sid)
    rows2 = await det.list_for_chat_session(sid)
    assert rows2[0]["ended_at"] is not None


@pytest.mark.asyncio
async def test_close_open_idempotent(migrated_db_path):
    sessions = SessionRepository(migrated_db_path)
    det = GameDetectionRepository(migrated_db_path)
    sid = await sessions.start_session()
    await det.close_open_for_chat_session(sid)
    await det.close_open_for_chat_session(sid)


@pytest.mark.asyncio
async def test_record_on_game_emit_closes_and_reopens(migrated_db_path):
    sessions = SessionRepository(migrated_db_path)
    det = GameDetectionRepository(migrated_db_path)
    chat_id = await sessions.start_session()
    ws = SimpleNamespace(_by_session={}, send_to_session=AsyncMock())
    ctx = SimpleNamespace(
        db_path=migrated_db_path,
        orchestrator=SimpleNamespace(
            state={"observer_active": True, "manual_game_profile_lock": False}
        ),
        db_session_by_ws={"w1": chat_id},
        websocket_manager=ws,
    )
    await record_game_detection_on_game_emit(
        ctx,
        {"game": "PoE2", "game_id": "poe2", "active": True},
    )
    rows = await det.list_for_chat_session(chat_id)
    assert len(rows) == 1
    assert rows[0]["game"] == "PoE2"

    await record_game_detection_on_game_emit(
        ctx,
        {"game": "Stellaris", "game_id": "stellaris", "active": True},
    )
    rows2 = await det.list_for_chat_session(chat_id)
    assert len(rows2) == 2
    assert rows2[0]["ended_at"] is not None
    assert rows2[1]["game"] == "Stellaris"
    assert rows2[1]["ended_at"] is None


@pytest.mark.asyncio
async def test_record_skips_when_observer_inactive(migrated_db_path):
    sessions = SessionRepository(migrated_db_path)
    det = GameDetectionRepository(migrated_db_path)
    chat_id = await sessions.start_session()
    ctx = SimpleNamespace(
        db_path=migrated_db_path,
        orchestrator=SimpleNamespace(
            state={"observer_active": False, "manual_game_profile_lock": False}
        ),
        db_session_by_ws={"w1": chat_id},
        websocket_manager=SimpleNamespace(_by_session={}, send_to_session=AsyncMock()),
    )
    await record_game_detection_on_game_emit(
        ctx,
        {"game": "PoE2", "active": True},
    )
    assert await det.list_for_chat_session(chat_id) == []


@pytest.mark.asyncio
async def test_observer_start_stop_command(migrated_db_path):
    sessions = SessionRepository(migrated_db_path)
    det = GameDetectionRepository(migrated_db_path)
    chat_id = await sessions.start_session()
    ctx = SimpleNamespace(
        db_path=migrated_db_path,
        orchestrator=SimpleNamespace(
            state={
                "observer_active": True,
                "manual_game_profile_lock": False,
                "current_game": "Cyberpunk 2077",
            }
        ),
        db_session_by_ws={"w1": chat_id},
    )
    await sync_game_detections_on_observer_command(ctx, "observer_start")
    rows = await det.list_for_chat_session(chat_id)
    assert len(rows) == 1
    assert rows[0]["ended_at"] is None

    await sync_game_detections_on_observer_command(ctx, "observer_stop")
    rows2 = await det.list_for_chat_session(chat_id)
    assert rows2[0]["ended_at"] is not None


@pytest.mark.asyncio
async def test_make_game_emitter_triggers_detection_row(migrated_db_path):
    sessions = SessionRepository(migrated_db_path)
    det = GameDetectionRepository(migrated_db_path)
    chat_id = await sessions.start_session()
    ws = SimpleNamespace(_by_session={}, send_to_session=AsyncMock())
    ctx = SimpleNamespace(
        db_path=migrated_db_path,
        config=ConfigSchema(),
        orchestrator=SimpleNamespace(
            state={"observer_active": True, "manual_game_profile_lock": True}
        ),
        db_session_by_ws={"w1": chat_id},
        websocket_manager=ws,
    )
    emit = make_game_emitter(ctx)
    await emit(
        "game_detected",
        {"game": "X", "game_id": "x", "active": True},
    )
    rows = await det.list_for_chat_session(chat_id)
    assert len(rows) == 1
    assert rows[0]["detection_method"] == "manual"
