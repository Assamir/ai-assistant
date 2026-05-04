from __future__ import annotations

from typing import Any, Dict, List, Optional

import aiosqlite

from backend.db.connection import apply_pragmas_async


class SessionRepository:
    """CRUD sesji zgodny z docs/DB_SCHEMA.md (sessions)."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def start_session(self, game_detected: Optional[str] = None) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute(
                """
                INSERT INTO sessions (started_at, game_detected, health_state)
                VALUES (unixepoch(), ?, 'healthy')
                """,
                (game_detected,),
            )
            await db.commit()
            cur = await db.execute("SELECT last_insert_rowid()")
            row = await cur.fetchone()
            return int(row[0])

    async def end_session(
        self,
        session_id: int,
        health_state: str = "healthy",
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute(
                """
                UPDATE sessions
                SET ended_at = unixepoch(), health_state = ?
                WHERE id = ?
                """,
                (health_state, session_id),
            )
            await db.commit()

    async def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, started_at, ended_at, game_detected, health_state
                FROM sessions WHERE id = ?
                """,
                (session_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return dict(row)

    async def delete_session(self, session_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            await db.commit()


class MessageRepository:
    """CRUD wiadomości zgodny z docs/DB_SCHEMA.md (messages)."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def create_message(
        self,
        session_id: int,
        source: str,
        content: str,
        *,
        emotion: Optional[str] = None,
        confidence_score: Optional[float] = None,
        include_in_semantic_memory: bool = False,
    ) -> int:
        if source not in ("user", "assistant", "observer", "system"):
            raise ValueError(f"Invalid message source: {source}")

        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute(
                """
                INSERT INTO messages (
                    session_id, source, content, emotion, confidence_score,
                    include_in_semantic_memory, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, unixepoch())
                """,
                (
                    session_id,
                    source,
                    content,
                    emotion,
                    confidence_score,
                    1 if include_in_semantic_memory else 0,
                ),
            )
            await db.commit()
            cur = await db.execute("SELECT last_insert_rowid()")
            row = await cur.fetchone()
            return int(row[0])

    async def get_messages_for_session(self, session_id: int) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, session_id, source, content, emotion, confidence_score,
                       include_in_semantic_memory, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (session_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_message(self, message_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, session_id, source, content, emotion, confidence_score,
                       include_in_semantic_memory, created_at
                FROM messages WHERE id = ?
                """,
                (message_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None


class SystemStateRepository:
    """Key-value stan systemu (system_state)."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def get_value(self, key: str) -> Optional[str]:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            cursor = await db.execute(
                "SELECT value FROM system_state WHERE key = ?", (key,)
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_value(self, key: str, value: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute(
                """
                INSERT INTO system_state (key, value, updated_at)
                VALUES (?, ?, unixepoch())
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = unixepoch()
                """,
                (key, value),
            )
            await db.commit()
