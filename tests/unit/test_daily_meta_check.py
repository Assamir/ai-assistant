"""Daily meta check helpers + ``DailyCheckRepository``."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.db.migration_runner import MigrationRunner
from backend.db.repositories import DailyCheckRepository
from backend.services.daily_meta_check import (
    _build_search_query,
    _summarize_search,
    write_daily_check_knowledge_note,
)


def test_build_search_query_inserts_league():
    q = _build_search_query("poe2", "Season 9", "")
    assert "poe2" in q.lower()
    assert "season 9" in q.lower()


def test_summarize_search_ok():
    text, has = _summarize_search(
        {
            "ok": True,
            "heading": "H",
            "abstract": "Body",
            "related_texts": ["r1"],
        }
    )
    assert "H" in text and "Body" in text
    assert has is True


def test_summarize_search_error():
    text, has = _summarize_search({"ok": False, "error": "timeout"})
    assert "timeout" in text
    assert has is False


def test_write_daily_check_knowledge_note_creates_file(tmp_path):
    root = Path(tmp_path)
    rel = write_daily_check_knowledge_note(
        root,
        knowledge_dir="knowledge",
        game_id="poe2",
        summary="Note body",
        query="q test",
    )
    assert rel is not None
    assert rel.startswith("knowledge/daily_checks/")
    assert rel.endswith(".md")
    full = (root / rel).resolve()
    assert full.is_file()
    text = full.read_text(encoding="utf-8")
    assert "Note body" in text
    assert "daily_check" in text


def test_write_daily_check_rejects_traversal(tmp_path):
    root = Path(tmp_path)
    assert write_daily_check_knowledge_note(root, knowledge_dir="../etc", game_id="x", summary="s", query="q") is None


@pytest.mark.asyncio
async def test_daily_check_repository_roundtrip(tmp_path):
    db_path = str(tmp_path / "d.db")
    MigrationRunner(db_path).run_migrations()
    repo = DailyCheckRepository(db_path)
    rid = await repo.insert_row(
        "poe2",
        result_summary="hello",
        has_changes=True,
    )
    assert rid >= 1
    latest = await repo.latest_checked_at("poe2")
    assert latest is not None
    rows = await repo.list_recent(game="poe2", limit=10)
    assert len(rows) == 1
    assert rows[0]["game"] == "poe2"
    assert rows[0]["result_summary"] == "hello"
