"""Testy CRUD SessionRepository i MessageRepository (tydzień 1 planu)."""

from __future__ import annotations

import pytest

from backend.db.repositories import MessageRepository, SessionRepository, SystemStateRepository


@pytest.mark.asyncio
async def test_session_start_and_get(migrated_db_path):
    repo = SessionRepository(migrated_db_path)
    sid = await repo.start_session(game_detected="Path of Exile 2")
    row = await repo.get_session(sid)
    assert row is not None
    assert row["id"] == sid
    assert row["game_detected"] == "Path of Exile 2"
    assert row["ended_at"] is None
    assert row["health_state"] == "healthy"


@pytest.mark.asyncio
async def test_session_end(migrated_db_path):
    repo = SessionRepository(migrated_db_path)
    sid = await repo.start_session()
    await repo.end_session(sid, health_state="crashed")
    row = await repo.get_session(sid)
    assert row["ended_at"] is not None
    assert row["health_state"] == "crashed"


@pytest.mark.asyncio
async def test_delete_empty_session(migrated_db_path):
    repo = SessionRepository(migrated_db_path)
    sid = await repo.start_session()
    await repo.delete_session(sid)
    assert await repo.get_session(sid) is None


@pytest.mark.asyncio
async def test_message_create_and_list(migrated_db_path):
    sessions = SessionRepository(migrated_db_path)
    messages = MessageRepository(migrated_db_path)
    sid = await sessions.start_session()

    mid = await messages.create_message(
        sid, "user", "Hej", confidence_score=0.91, emotion="neutral"
    )
    assert mid >= 1

    listed = await messages.get_messages_for_session(sid)
    assert len(listed) == 1
    assert listed[0]["content"] == "Hej"
    assert listed[0]["source"] == "user"
    assert listed[0]["confidence_score"] == pytest.approx(0.91)
    assert listed[0]["emotion"] == "neutral"

    one = await messages.get_message(mid)
    assert one is not None
    assert one["id"] == mid


@pytest.mark.asyncio
async def test_message_invalid_source(migrated_db_path):
    sessions = SessionRepository(migrated_db_path)
    messages = MessageRepository(migrated_db_path)
    sid = await sessions.start_session()
    with pytest.raises(ValueError, match="Invalid message source"):
        await messages.create_message(sid, "player", "x")


@pytest.mark.asyncio
async def test_messages_ordered_by_created_at(migrated_db_path):
    sessions = SessionRepository(migrated_db_path)
    messages = MessageRepository(migrated_db_path)
    sid = await sessions.start_session()
    await messages.create_message(sid, "user", "A")
    await messages.create_message(sid, "assistant", "B")
    rows = await messages.get_messages_for_session(sid)
    assert [r["content"] for r in rows] == ["A", "B"]


@pytest.mark.asyncio
async def test_system_state_roundtrip(migrated_db_path):
    repo = SystemStateRepository(migrated_db_path)
    assert await repo.get_value("audio_mode") == "ptt"
    await repo.set_value("audio_mode", "wakeword")
    assert await repo.get_value("audio_mode") == "wakeword"


@pytest.mark.asyncio
async def test_migration_runner_idempotent(migrated_db_path):
    from pathlib import Path

    from backend.db.migration_runner import MigrationRunner

    p = Path(migrated_db_path)
    MigrationRunner(str(p)).run_migrations()
    MigrationRunner(str(p)).run_migrations()
    runner = MigrationRunner(str(p))
    st = runner.get_migration_status()
    assert st["current_version"] >= 1
