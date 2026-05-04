"""SessionWatchdog — recovery po crashu, synchronizacja stanu CB, wykrycie hibernacji."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from typing import Awaitable, Callable, Optional

from backend.db.connection import apply_pragmas_sync
from backend.db.repositories import SystemStateRepository

logger = logging.getLogger(__name__)

RecoverHook = Optional[Callable[[], Awaitable[None]]]


def recover_stale_sessions(db_path: str) -> list[int]:
    """
    Przy starcie: zamknięcie sesji DB z nieustawionym `ended_at` (poprzedni proces padł).
    Zwraca listę ID sesji oznaczonych jako crashed.
    """
    conn = sqlite3.connect(db_path)
    ids: list[int] = []
    try:
        apply_pragmas_sync(conn)
        cur = conn.cursor()
        cur.execute("SELECT id FROM sessions WHERE ended_at IS NULL")
        ids = [int(row[0]) for row in cur.fetchall()]
        for sid in ids:
            cur.execute(
                """
                UPDATE sessions
                SET ended_at = unixepoch(), health_state = 'crashed'
                WHERE id = ?
                """,
                (sid,),
            )
        if ids:
            cur.execute(
                """
                INSERT INTO health_events (component, event_type, details, created_at)
                VALUES ('startup', 'crash_recovery', ?, unixepoch())
                """,
                (json.dumps({"recovered_session_ids": ids}),),
            )
        conn.commit()
        if ids:
            logger.warning("Crash recovery: closed %d stale session(s): %s", len(ids), ids)
        return ids
    finally:
        conn.close()


class SessionWatchdog:
    """Pętla w tle: sync circuit breaker → system_state, wykrycie hibernacji (dryf zegara)."""

    def __init__(
        self,
        *,
        db_path: str,
        llm_client: Optional[object] = None,
        interval_seconds: float = 30.0,
        hibernation_drift_seconds: float = 35.0,
        on_hibernation: RecoverHook = None,
    ) -> None:
        self._db_path = db_path
        self._llm = llm_client
        self._interval = interval_seconds
        self._hibernation_threshold = hibernation_drift_seconds
        self._on_hibernation = on_hibernation
        self._stop = asyncio.Event()
        self._last_mono: Optional[float] = None
        self._last_wall: Optional[float] = None
        self._prev_breaker_fingerprint: Optional[tuple[str, int]] = None

    def stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        while not self._stop.is_set():
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("SessionWatchdog tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval)
                break
            except asyncio.TimeoutError:
                continue

    async def _tick(self) -> None:
        mono = time.monotonic()
        wall = time.time()

        if (
            self._last_mono is not None
            and self._last_wall is not None
            and self._on_hibernation is not None
        ):
            drift = (wall - self._last_wall) - (mono - self._last_mono)
            if drift > self._hibernation_threshold:
                try:
                    await self._on_hibernation()
                except Exception:
                    logger.exception("hibernation hook failed")
                await self._record_hibernation_event(drift)

        self._last_mono = mono
        self._last_wall = wall

        breaker = getattr(self._llm, "_breaker", None) if self._llm else None
        if breaker is None:
            return
        state = str(getattr(breaker, "state", ""))
        failures = int(getattr(breaker, "failure_count", 0))
        fp = (state, failures)
        if fp == self._prev_breaker_fingerprint:
            return
        self._prev_breaker_fingerprint = fp
        repo = SystemStateRepository(self._db_path)
        await repo.set_value("circuit_breaker_state", state)
        await repo.set_value("circuit_breaker_failures", str(failures))
        await repo.set_value("circuit_breaker_last_fail", str(int(wall)))

    async def _record_hibernation_event(self, drift: float) -> None:
        repo = SystemStateRepository(self._db_path)
        await repo.set_value("last_hibernation_drift_seconds", f"{drift:.1f}")
        conn = sqlite3.connect(self._db_path)
        try:
            apply_pragmas_sync(conn)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO health_events (component, event_type, details, created_at)
                VALUES ('watchdog', 'hibernation_suspected', ?, unixepoch())
                """,
                (json.dumps({"wall_clock_drift_seconds": drift}),),
            )
            conn.commit()
        finally:
            conn.close()


__all__ = ["SessionWatchdog", "recover_stale_sessions"]
