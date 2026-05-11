"""Zarządza cyklem życia wątków konwersacji."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from backend.core.thread_classifier import ClassificationResult, ThreadClassifier

_logger = logging.getLogger(__name__)


class ThreadContext:
    """Kontekst wątku do wstrzyknięcia w prompt."""

    __slots__ = ("thread_id", "title", "topic_summary", "key_decisions", "key_directions", "kind")

    def __init__(
        self,
        thread_id: int,
        *,
        title: Optional[str],
        topic_summary: Optional[str],
        key_decisions: list[str],
        key_directions: list[str],
        kind: str = "continuation",
    ) -> None:
        self.thread_id = thread_id
        self.title = title
        self.topic_summary = topic_summary
        self.key_decisions = key_decisions
        self.key_directions = key_directions
        self.kind = kind

    def to_prompt_block(self, message_count: int = 0) -> str:
        lines = []
        title = self.title or "Bez tytułu"
        lines.append(f"## AKTYWNY WĄTEK: {title}")
        if self.topic_summary:
            lines.append(f"\nTematyka: {self.topic_summary}")
        if self.key_decisions:
            lines.append("\nPodjęte decyzje:")
            for d in self.key_decisions[:5]:
                lines.append(f"- {d}")
        if self.key_directions:
            lines.append("\nAktualny kierunek:")
            for d in self.key_directions[:3]:
                lines.append(f"- {d}")
        if message_count:
            lines.append(f"\n(Wątek: {message_count} wiadomości)")
        lines.append(
            "\nNarzędzia wątkowe: `thread_add_decision` gdy coś postanowiono, "
            "`thread_add_direction` gdy zmienia się cel, "
            "`thread_summarize` gdy warto zaktualizować tytuł/tematykę."
        )
        return "\n".join(lines)


class ThreadManager:
    """Tworzy, klasyfikuje i aktualizuje wątki na podstawie każdej wiadomości."""

    SUMMARY_INTERVAL = 10

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._classifier = ThreadClassifier(db_path)

    async def handle_message(
        self,
        message: str,
        *,
        active_thread_id: Optional[int],
        message_id: Optional[int] = None,
    ) -> tuple[ClassificationResult, int]:
        """Klasyfikuje wiadomość i zwraca (result, thread_id)."""
        from backend.db.repositories import ThreadRepository

        repo = ThreadRepository(self._db_path)
        result = await self._classifier.classify(message, active_thread_id)

        if result.kind == "new":
            thread_id = await repo.create_thread()
        elif result.kind == "resumed":
            thread_id = result.thread_id  # type: ignore[assignment]
            await repo.update_thread(thread_id, status="active")
        else:
            thread_id = active_thread_id  # type: ignore[assignment]
            if thread_id is None:
                thread_id = await repo.create_thread()

        await repo.touch(thread_id)
        await repo.increment_message_count(thread_id)

        if message_id is not None:
            await repo.add_message_to_thread(message_id, thread_id)

        count = (await repo.get_thread(thread_id) or {}).get("message_count", 0)
        if count == 3:
            await self._generate_initial_title(thread_id, message, repo)
        elif count > 3 and count % self.SUMMARY_INTERVAL == 0:
            await self._refresh_summary(thread_id, repo)

        return result, thread_id

    async def pause_thread(self, thread_id: int) -> None:
        from backend.db.repositories import ThreadRepository
        await ThreadRepository(self._db_path).update_thread(thread_id, status="paused")

    async def get_context(self, thread_id: int, kind: str = "continuation") -> Optional[ThreadContext]:
        from backend.db.repositories import ThreadRepository
        thread = await ThreadRepository(self._db_path).get_thread(thread_id)
        if thread is None:
            return None
        try:
            decisions = json.loads(thread.get("key_decisions") or "[]")
            directions = json.loads(thread.get("key_directions") or "[]")
        except (json.JSONDecodeError, TypeError):
            decisions, directions = [], []
        return ThreadContext(
            thread_id=thread_id,
            title=thread.get("title"),
            topic_summary=thread.get("topic_summary"),
            key_decisions=decisions if isinstance(decisions, list) else [],
            key_directions=directions if isinstance(directions, list) else [],
            kind=kind,
        )

    async def add_decision(self, thread_id: int, decision: str) -> None:
        from backend.db.repositories import ThreadRepository
        repo = ThreadRepository(self._db_path)
        thread = await repo.get_thread(thread_id)
        if thread is None:
            return
        try:
            decisions = json.loads(thread.get("key_decisions") or "[]")
        except (json.JSONDecodeError, TypeError):
            decisions = []
        if not isinstance(decisions, list):
            decisions = []
        decisions.append(str(decision).strip())
        await repo.update_thread(thread_id, key_decisions=json.dumps(decisions, ensure_ascii=False))

    async def add_direction(self, thread_id: int, direction: str) -> None:
        from backend.db.repositories import ThreadRepository
        repo = ThreadRepository(self._db_path)
        thread = await repo.get_thread(thread_id)
        if thread is None:
            return
        try:
            directions = json.loads(thread.get("key_directions") or "[]")
        except (json.JSONDecodeError, TypeError):
            directions = []
        if not isinstance(directions, list):
            directions = []
        directions.append(str(direction).strip())
        await repo.update_thread(thread_id, key_directions=json.dumps(directions, ensure_ascii=False))

    async def update_summary(
        self,
        thread_id: int,
        *,
        title: Optional[str] = None,
        topic_summary: Optional[str] = None,
    ) -> None:
        from backend.db.repositories import ThreadRepository
        updates: Dict[str, Any] = {}
        if title is not None:
            updates["title"] = title
        if topic_summary is not None:
            updates["topic_summary"] = topic_summary
        if updates:
            await ThreadRepository(self._db_path).update_thread(thread_id, **updates)

    async def _generate_initial_title(self, thread_id: int, message: str, repo: Any) -> None:
        short = (message[:80] + "…") if len(message) > 80 else message
        await repo.update_thread(thread_id, title=short)

    async def _refresh_summary(self, thread_id: int, repo: Any) -> None:
        """Buduje streszczenie z ostatnich wiadomości użytkownika w wątku."""
        try:
            import aiosqlite
            from backend.db.connection import apply_pragmas_async

            async with aiosqlite.connect(self._db_path) as db:
                await apply_pragmas_async(db)
                cur = await db.execute(
                    """
                    SELECT m.source, m.content
                    FROM thread_messages tm
                    JOIN messages m ON m.id = tm.message_id
                    WHERE tm.thread_id = ? AND m.source IN ('user', 'assistant')
                    ORDER BY m.id DESC
                    LIMIT 20
                    """,
                    (thread_id,),
                )
                rows = await cur.fetchall()

            if not rows:
                return

            user_snippets = [
                row[1][:120].strip()
                for row in reversed(rows)
                if row[0] == "user" and row[1].strip()
            ]
            if not user_snippets:
                return

            summary = "; ".join(user_snippets[-6:])
            if len(summary) > 400:
                summary = summary[:397] + "…"

            await repo.update_thread(thread_id, topic_summary=summary)
        except Exception:
            pass


__all__ = ["ThreadManager", "ThreadContext"]
