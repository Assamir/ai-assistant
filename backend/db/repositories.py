from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

import aiosqlite

from backend.db.connection import apply_pragmas_async

DetectionMethod = Literal["process", "vlm", "manual"]
SnapshotTrigger = Literal["session_start", "character_change", "game_detected"]
ArchiveReason = Literal["season_reset", "manual", "backup"]


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

    async def list_for_chat_after_message(
        self,
        chat_session_id: int,
        after_message_id_exclusive: int,
    ) -> List[Dict[str, Any]]:
        """Wszystkie `tool_calls` powiązane z wiadomościami w sesji czatu utworzonymi po danym `messages.id`."""
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT tc.id, tc.message_id, tc.turn_sequence, tc.tool_name, tc.input_json,
                       tc.output_json, tc.duration_ms, tc.success, tc.error_message, tc.created_at
                FROM tool_calls tc
                INNER JOIN messages m ON m.id = tc.message_id
                WHERE m.session_id = ? AND m.id > ?
                ORDER BY tc.id ASC
                """,
                (chat_session_id, after_message_id_exclusive),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


class PlayerContextSnapshotRepository:
    """INSERT do ``player_context_snapshots`` (DOK / DB_SCHEMA)."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def insert(
        self,
        session_id: int,
        game: str,
        active_character: str,
        *,
        trigger: SnapshotTrigger,
        character_class: Optional[str] = None,
        build_name: Optional[str] = None,
        build_url: Optional[str] = None,
        league: Optional[str] = None,
    ) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute(
                """
                INSERT INTO player_context_snapshots (
                    session_id, game, active_character, character_class,
                    build_name, build_url, league, trigger, captured_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, unixepoch())
                """,
                (
                    session_id,
                    game,
                    active_character,
                    character_class,
                    build_name,
                    build_url,
                    league,
                    trigger,
                ),
            )
            await db.commit()
            cur = await db.execute("SELECT last_insert_rowid()")
            row = await cur.fetchone()
            return int(row[0])


class PlayerProfileArchiveRepository:
    """INSERT / SELECT dla ``player_profile_archives`` (reset sezonu, ręcznie, backup)."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def insert(
        self,
        game: str,
        season: str,
        yaml_snapshot: str,
        reason: ArchiveReason,
    ) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute(
                """
                INSERT INTO player_profile_archives (game, season, yaml_snapshot, reason, archive_date)
                VALUES (?, ?, ?, ?, unixepoch())
                """,
                (game, season, yaml_snapshot, reason),
            )
            await db.commit()
            cur = await db.execute("SELECT last_insert_rowid()")
            row = await cur.fetchone()
            return int(row[0])

    async def list_recent(
        self,
        *,
        game: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        cap = max(1, min(int(limit), 200))
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            if game and str(game).strip():
                cursor = await db.execute(
                    """
                    SELECT id, game, season, reason, archive_date, yaml_snapshot
                    FROM player_profile_archives
                    WHERE game = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (str(game).strip(), cap),
                )
            else:
                cursor = await db.execute(
                    """
                    SELECT id, game, season, reason, archive_date, yaml_snapshot
                    FROM player_profile_archives
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (cap,),
                )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


class DailyCheckRepository:
    """Tabela ``daily_checks`` — śledzenie codziennego meta check (PRD §6.2)."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def insert_row(
        self,
        game: str,
        *,
        result_summary: Optional[str] = None,
        knowledge_file_path: Optional[str] = None,
        has_changes: bool = False,
        user_notified: bool = False,
    ) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute(
                """
                INSERT INTO daily_checks (
                    game, checked_at, result_summary, knowledge_file_path, has_changes, user_notified
                )
                VALUES (?, unixepoch(), ?, ?, ?, ?)
                """,
                (
                    game,
                    result_summary,
                    knowledge_file_path,
                    1 if has_changes else 0,
                    1 if user_notified else 0,
                ),
            )
            await db.commit()
            cur = await db.execute("SELECT last_insert_rowid()")
            row = await cur.fetchone()
            return int(row[0])

    async def latest_checked_at(self, game: str) -> Optional[int]:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            cur = await db.execute(
                """
                SELECT checked_at FROM daily_checks
                WHERE game = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (game,),
            )
            row = await cur.fetchone()
            return int(row[0]) if row else None

    async def list_recent(
        self,
        *,
        game: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        cap = max(1, min(int(limit), 200))
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            if game and str(game).strip():
                cursor = await db.execute(
                    """
                    SELECT id, game, checked_at, result_summary, knowledge_file_path,
                           has_changes, user_notified
                    FROM daily_checks
                    WHERE game = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (str(game).strip(), cap),
                )
            else:
                cursor = await db.execute(
                    """
                    SELECT id, game, checked_at, result_summary, knowledge_file_path,
                           has_changes, user_notified
                    FROM daily_checks
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (cap,),
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


class ThreadRepository:
    """CRUD wątków konwersacji (conversation_threads + thread_messages)."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    async def create_thread(self, title: Optional[str] = None) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute(
                """
                INSERT INTO conversation_threads (title, status, created_at, updated_at, last_active_at)
                VALUES (?, 'active', unixepoch(), unixepoch(), unixepoch())
                """,
                (title,),
            )
            await db.commit()
            cur = await db.execute("SELECT last_insert_rowid()")
            row = await cur.fetchone()
            return int(row[0])

    async def get_thread(self, thread_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT id, title, status, topic_summary, key_decisions, key_directions,
                       message_count, created_at, updated_at, last_active_at
                FROM conversation_threads WHERE id = ?
                """,
                (thread_id,),
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def update_thread(self, thread_id: int, **kwargs: Any) -> None:
        allowed = {"title", "status", "topic_summary", "key_decisions", "key_directions"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        set_clause += ", updated_at = unixepoch()"
        values = list(updates.values()) + [thread_id]
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute(
                f"UPDATE conversation_threads SET {set_clause} WHERE id = ?",
                values,
            )
            await db.commit()

    async def touch(self, thread_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute(
                "UPDATE conversation_threads SET last_active_at = unixepoch() WHERE id = ?",
                (thread_id,),
            )
            await db.commit()

    async def increment_message_count(self, thread_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute(
                "UPDATE conversation_threads SET message_count = message_count + 1 WHERE id = ?",
                (thread_id,),
            )
            await db.commit()

    async def add_message_to_thread(self, message_id: int, thread_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute(
                "INSERT OR IGNORE INTO thread_messages (message_id, thread_id) VALUES (?, ?)",
                (message_id, thread_id),
            )
            await db.commit()

    async def get_recent_paused_threads(self, days: int = 30) -> List[Dict[str, Any]]:
        cutoff = int(__import__("time").time()) - days * 86400
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT id, title, status, topic_summary, key_decisions, key_directions,
                       message_count, last_active_at
                FROM conversation_threads
                WHERE status = 'paused' AND last_active_at >= ?
                ORDER BY last_active_at DESC
                LIMIT 20
                """,
                (cutoff,),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def list_by_status(self, status: str) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT id, title, status, topic_summary, key_decisions, key_directions,
                       message_count, last_active_at
                FROM conversation_threads
                WHERE status = ?
                ORDER BY last_active_at DESC
                LIMIT 50
                """,
                (status,),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def list_for_panel(self, limit: int = 20) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT id, title, status, topic_summary, message_count, last_active_at
                FROM conversation_threads
                ORDER BY last_active_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 100)),),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


class AgentTaskRepository:
    """CRUD zadań agentowych (agent_tasks)."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    async def create_task(
        self,
        *,
        session_id: Optional[int],
        thread_id: Optional[int],
        goal_text: str,
        step_index: int,
        total_steps: int,
        description: str,
    ) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute(
                """
                INSERT INTO agent_tasks (
                    session_id, thread_id, goal_text, step_index, total_steps,
                    description, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'pending', unixepoch(), unixepoch())
                """,
                (session_id, thread_id, goal_text, step_index, total_steps, description),
            )
            await db.commit()
            cur = await db.execute("SELECT last_insert_rowid()")
            row = await cur.fetchone()
            return int(row[0])

    async def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT id, session_id, thread_id, goal_text, step_index, total_steps,
                       description, status, result_summary, quality_score, created_at, updated_at
                FROM agent_tasks WHERE id = ?
                """,
                (task_id,),
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def update_task(self, task_id: int, **kwargs: Any) -> None:
        allowed = {"status", "result_summary", "quality_score"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        set_clause += ", updated_at = unixepoch()"
        values = list(updates.values()) + [task_id]
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute(
                f"UPDATE agent_tasks SET {set_clause} WHERE id = ?",
                values,
            )
            await db.commit()

    async def list_for_session(self, session_id: int) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT id, goal_text, step_index, total_steps, description,
                       status, result_summary, quality_score, created_at
                FROM agent_tasks
                WHERE session_id = ?
                ORDER BY created_at DESC, step_index ASC
                LIMIT 100
                """,
                (session_id,),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


class AgentNoteRepository:
    """CRUD notatek agentowych (agent_notes)."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    async def save_note(
        self,
        *,
        session_id: Optional[int],
        task_id: Optional[int],
        thread_id: Optional[int],
        content: str,
    ) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            await db.execute(
                """
                INSERT INTO agent_notes (session_id, task_id, thread_id, content, created_at)
                VALUES (?, ?, ?, ?, unixepoch())
                """,
                (session_id, task_id, thread_id, content),
            )
            await db.commit()
            cur = await db.execute("SELECT last_insert_rowid()")
            row = await cur.fetchone()
            return int(row[0])

    async def get_notes_for_session(self, session_id: int) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT id, task_id, thread_id, content, created_at
                FROM agent_notes
                WHERE session_id = ?
                ORDER BY created_at ASC
                LIMIT 50
                """,
                (session_id,),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def get_notes_for_task(self, task_id: int) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            await apply_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT id, content, created_at
                FROM agent_notes
                WHERE task_id = ?
                ORDER BY created_at ASC
                """,
                (task_id,),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
