"""Daily meta check helpers + ``DailyCheckRepository``."""

from __future__ import annotations

import pytest

from backend.db.migration_runner import MigrationRunner
from backend.db.repositories import DailyCheckRepository
from backend.services.daily_meta_check import _build_search_query, _summarize_search


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
