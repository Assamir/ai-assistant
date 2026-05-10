"""Klasyfikator wątków konwersacji: nowy / kontynuacja / reaktywacja."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

_STOP_WORDS = frozenset(
    "a ale bo czy da dla do i jak już jest jak jestem może na nie no o po przez"
    " się so tak też to w we z że ze".split()
)


def _token_set(text: str) -> frozenset[str]:
    words = re.findall(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{3,}", text.lower())
    return frozenset(w for w in words if w not in _STOP_WORDS)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


RESUME_PATTERNS = re.compile(
    r"wróćmy|wróć|powróćmy|wróć do|tamten temat|poprzedni temat|"
    r"o czym mówiliśmy|wcześniej rozmawialiśmy|pamiętasz.*rozmawialiśmy",
    re.IGNORECASE,
)

CONTINUATION_THRESHOLD = 0.25
PAUSED_RESUME_THRESHOLD = 0.35
RECENT_MINUTES = 30


@dataclass
class ClassificationResult:
    kind: str  # "new" | "continuation" | "resumed"
    thread_id: Optional[int]
    confidence: float


class ThreadClassifier:
    """Klasyfikuje wiadomość jako nowy wątek, kontynuację lub reaktywację."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def classify(
        self,
        message: str,
        active_thread_id: Optional[int],
    ) -> ClassificationResult:
        from backend.db.repositories import ThreadRepository

        repo = ThreadRepository(self._db_path)
        msg_tokens = _token_set(message)

        if RESUME_PATTERNS.search(message):
            paused = await repo.get_recent_paused_threads(days=30)
            best = self._best_match(msg_tokens, paused)
            if best and best[1] >= 0.1:
                return ClassificationResult("resumed", best[0]["id"], best[1])

        if active_thread_id is not None:
            thread = await repo.get_thread(active_thread_id)
            if thread is not None and thread.get("status") == "active":
                age_s = time.time() - (thread.get("last_active_at") or 0)
                summary_tokens = _token_set(
                    str(thread.get("topic_summary") or "")
                    + " "
                    + str(thread.get("title") or "")
                )
                similarity = _jaccard(msg_tokens, summary_tokens)

                if age_s < RECENT_MINUTES * 60:
                    if similarity >= CONTINUATION_THRESHOLD or age_s < 300:
                        return ClassificationResult("continuation", active_thread_id, max(similarity, 0.5))
                else:
                    if similarity >= CONTINUATION_THRESHOLD * 2:
                        return ClassificationResult("continuation", active_thread_id, similarity)

        paused = await repo.get_recent_paused_threads(days=30)
        best = self._best_match(msg_tokens, paused)
        if best and best[1] >= PAUSED_RESUME_THRESHOLD:
            return ClassificationResult("resumed", best[0]["id"], best[1])

        return ClassificationResult("new", None, 1.0)

    @staticmethod
    def _best_match(
        msg_tokens: frozenset[str],
        threads: List[Dict[str, Any]],
    ) -> Optional[tuple[Dict[str, Any], float]]:
        best_score = 0.0
        best_thread: Optional[Dict[str, Any]] = None
        for t in threads:
            t_tokens = _token_set(
                str(t.get("topic_summary") or "")
                + " "
                + str(t.get("title") or "")
                + " "
                + str(t.get("key_decisions") or "")
            )
            score = _jaccard(msg_tokens, t_tokens)
            if score > best_score:
                best_score = score
                best_thread = t
        if best_thread is None:
            return None
        return best_thread, best_score


__all__ = ["ThreadClassifier", "ClassificationResult"]
