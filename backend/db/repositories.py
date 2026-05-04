from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

import aiosqlite

from backend.db.connection import apply_pragmas_async

DetectionMethod = Literal["process", "vlm", "manual"]


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


class ToolCallsRepository:
    """Wiersze `tool_calls` — log narzędzi MCP powiązany z wiadomością asystenta (DOK-10)."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def insert_completed(
        self,
        message_id: int,
        turn_sequence: int,
        tool_name: str,
        input_json: str,
        output_json: Optional[str],
        duration_ms: int,
        success: bool,
        error_message: Optional[str] = None,
    ) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute(
                """
                INSERT INTO tool_calls (
                    message_id, turn_sequence, tool_name, input_json,
                    output_json, duration_ms, success, error_message, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, unixepoch())
                """,
                (
                    message_id,
                    turn_sequence,
                    tool_name,
                    input_json,
                    output_json,
                    int(duration_ms),
                    1 if success else 0,
                    error_message,
                ),
            )
            await db.commit()
            cur = await db.execute("SELECT last_insert_rowid()")
            row = await cur.fetchone()
            return int(row[0])

    async def list_for_message(self, message_id: int) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, message_id, turn_sequence, tool_name, input_json,
                       output_json, duration_ms, success, error_message, created_at
                FROM tool_calls
                WHERE message_id = ?
                ORDER BY turn_sequence ASC, id ASC
                """,
                (message_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


class GameDetectionRepository:
    """Wiersze `game_detections` — sesja czatu SQLite (`sessions.id`)."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def close_open_for_chat_session(self, chat_session_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute(
                """
                UPDATE game_detections
                SET ended_at = unixepoch()
                WHERE session_id = ? AND ended_at IS NULL
                """,
                (chat_session_id,),
            )
            await db.commit()

    async def start_detection(
        self,
        chat_session_id: int,
        game: str,
        *,
        process_name: Optional[str] = None,
        detection_method: DetectionMethod = "process",
    ) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute(
                """
                INSERT INTO game_detections (
                    session_id, game, process_name, detection_method, started_at
                )
                VALUES (?, ?, ?, ?, unixepoch())
                """,
                (chat_session_id, game, process_name, detection_method),
            )
            await db.commit()
            cur = await db.execute("SELECT last_insert_rowid()")
            row = await cur.fetchone()
            return int(row[0])

    async def list_for_chat_session(self, chat_session_id: int) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, session_id, game, process_name, detection_method,
                       started_at, ended_at
                FROM game_detections
                WHERE session_id = ?
                ORDER BY started_at ASC, id ASC
                """,
                (chat_session_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


class MCPCacheRepository:
    """Tabela `mcp_cache` — SHA256 cache_key, TTL od `created_at`."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def get_fresh_json(self, tool_name: str, cache_key: str) -> Optional[str]:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT id, response_json
                FROM mcp_cache
                WHERE tool_name = ? AND cache_key = ?
                  AND (unixepoch() - created_at) < ttl_seconds
                """,
                (tool_name, cache_key),
            )
            row = await cur.fetchone()
            if row is None:
                return None
            row_id = int(row["id"])
            await db.execute(
                "UPDATE mcp_cache SET hit_count = hit_count + 1 WHERE id = ?",
                (row_id,),
            )
            await db.commit()
            return str(row["response_json"])

    async def put_json(
        self,
        tool_name: str,
        cache_key: str,
        response_json: str,
        ttl_seconds: int,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute(
                """
                INSERT INTO mcp_cache (
                    tool_name, cache_key, response_json, ttl_seconds, hit_count, created_at
                )
                VALUES (?, ?, ?, ?, 0, unixepoch())
                ON CONFLICT(cache_key) DO UPDATE SET
                    tool_name = excluded.tool_name,
                    response_json = excluded.response_json,
                    ttl_seconds = excluded.ttl_seconds,
                    hit_count = 0,
                    created_at = unixepoch()
                """,
                (tool_name, cache_key, response_json, ttl_seconds),
            )
            await db.commit()

    async def invalidate_all(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute("DELETE FROM mcp_cache")
            await db.commit()


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
