"""Crash recovery przy starcie (sesje DB)."""

from __future__ import annotations

import sqlite3

import pytest

from backend.db.connection import apply_pragmas_sync
from backend.db.migration_runner import MigrationRunner
from backend.services.session_watchdog import recover_stale_sessions


@pytest.fixture
def db_with_open_session(tmp_path):
    p = tmp_path / "t.db"
    MigrationRunner(str(p)).run_migrations()
    conn = sqlite3.connect(str(p))
    try:
        apply_pragmas_sync(conn)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO sessions (started_at, health_state) VALUES (unixepoch(), 'healthy')"
        )
        conn.commit()
    finally:
        conn.close()
    return str(p)


def test_recover_stale_sessions_closes_open_rows(db_with_open_session):
    ids = recover_stale_sessions(db_with_open_session)
    assert len(ids) == 1
    conn = sqlite3.connect(db_with_open_session)
    try:
        cur = conn.cursor()
        cur.execute("SELECT ended_at, health_state FROM sessions WHERE id = ?", (ids[0],))
        row = cur.fetchone()
        assert row is not None
        assert row[0] is not None
        assert row[1] == "crashed"
    finally:
        conn.close()


def test_recover_stale_sessions_idempotent(db_with_open_session):
    recover_stale_sessions(db_with_open_session)
    again = recover_stale_sessions(db_with_open_session)
    assert again == []
