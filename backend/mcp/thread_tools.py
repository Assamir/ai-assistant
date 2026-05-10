"""Narzędzia MCP do zarządzania wątkami konwersacji (System B)."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, MutableMapping, Optional

_TOOL_THREAD_ADD_DECISION = {
    "type": "function",
    "function": {
        "name": "thread_add_decision",
        "description": (
            "Zapisuje konkretną decyzję podjętą w bieżącym wątku konwersacji. "
            "Użyj gdy użytkownik lub asystent dochodzi do konkretnej konkluzji, np. 'wybieramy Amumu'. "
            "Decyzje są wstrzykiwane do kontekstu przyszłych wiadomości."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "decision": {
                    "type": "string",
                    "description": "Krótka, konkretna decyzja (1-2 zdania).",
                },
            },
            "required": ["decision"],
        },
    },
}

_TOOL_THREAD_ADD_DIRECTION = {
    "type": "function",
    "function": {
        "name": "thread_add_direction",
        "description": (
            "Zapisuje aktualny kierunek / niezakończony cel wątku konwersacji. "
            "Użyj gdy rozmowa ma określony cel, który jeszcze nie jest osiągnięty, "
            "np. 'szukamy ADC komplementarnego do engage'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "description": "Aktualny kierunek lub niezakończony cel (1-2 zdania).",
                },
            },
            "required": ["direction"],
        },
    },
}

_TOOL_THREAD_SUMMARIZE = {
    "type": "function",
    "function": {
        "name": "thread_summarize",
        "description": (
            "Aktualizuje streszczenie i tytuł aktywnego wątku konwersacji. "
            "Wywołaj po dłuższej wymianie zdań, aby zachować kontekst dla przyszłych sesji."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Krótki tytuł wątku (5-10 słów).",
                },
                "summary": {
                    "type": "string",
                    "description": "2-3 zdaniowe streszczenie wątku.",
                },
            },
            "required": ["title", "summary"],
        },
    },
}

_TOOL_THREAD_SEARCH = {
    "type": "function",
    "function": {
        "name": "thread_search",
        "description": (
            "Wyszukuje historyczne wątki konwersacji pasujące do zapytania. "
            "Użyj gdy użytkownik chce wrócić do poprzedniego tematu."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Słowa kluczowe opisujące szukany wątek.",
                },
            },
            "required": ["query"],
        },
    },
}

_TOOL_THREAD_RESUME = {
    "type": "function",
    "function": {
        "name": "thread_resume",
        "description": (
            "Reaktywuje wskazany wątek z historii. "
            "Wywołaj po thread_search gdy użytkownik chce wróć do konkretnego wątku."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "thread_id": {
                    "type": "integer",
                    "description": "ID wątku do reaktywacji (z wyników thread_search).",
                },
            },
            "required": ["thread_id"],
        },
    },
}


def make_thread_tools(
    db_path: str,
    orchestrator_state: MutableMapping[str, Any],
) -> Dict[str, tuple[Dict[str, Any], Callable[..., Any]]]:
    """Zwraca słownik {nazwa: (schema, handler)} dla narzędzi wątkowych."""

    async def tool_thread_add_decision(decision: str) -> Dict[str, Any]:
        thread_id = orchestrator_state.get("active_thread_id")
        if not isinstance(thread_id, int):
            return {"ok": False, "error": "Brak aktywnego wątku."}
        from backend.core.thread_manager import ThreadManager
        await ThreadManager(db_path).add_decision(thread_id, decision)
        return {"ok": True, "thread_id": thread_id, "decision": decision}

    async def tool_thread_add_direction(direction: str) -> Dict[str, Any]:
        thread_id = orchestrator_state.get("active_thread_id")
        if not isinstance(thread_id, int):
            return {"ok": False, "error": "Brak aktywnego wątku."}
        from backend.core.thread_manager import ThreadManager
        await ThreadManager(db_path).add_direction(thread_id, direction)
        return {"ok": True, "thread_id": thread_id, "direction": direction}

    async def tool_thread_summarize(title: str, summary: str) -> Dict[str, Any]:
        thread_id = orchestrator_state.get("active_thread_id")
        if not isinstance(thread_id, int):
            return {"ok": False, "error": "Brak aktywnego wątku."}
        from backend.core.thread_manager import ThreadManager
        await ThreadManager(db_path).update_summary(thread_id, title=title, topic_summary=summary)
        return {"ok": True, "thread_id": thread_id, "title": title}

    async def tool_thread_search(query: str) -> Dict[str, Any]:
        from backend.db.repositories import ThreadRepository
        from backend.core.thread_classifier import _token_set, _jaccard

        repo = ThreadRepository(db_path)
        paused = await repo.get_recent_paused_threads(days=30)
        active_list = await repo.list_by_status("active")
        all_threads = paused + [t for t in active_list if t not in paused]

        q_tokens = _token_set(query)
        scored = []
        for t in all_threads:
            t_tokens = _token_set(
                str(t.get("topic_summary") or "")
                + " "
                + str(t.get("title") or "")
                + " "
                + str(t.get("key_decisions") or "")
            )
            score = _jaccard(q_tokens, t_tokens)
            scored.append({
                "thread_id": t["id"],
                "title": t.get("title") or "(bez tytułu)",
                "summary": t.get("topic_summary"),
                "status": t.get("status"),
                "message_count": t.get("message_count", 0),
                "relevance": round(score, 3),
            })

        scored.sort(key=lambda x: x["relevance"], reverse=True)
        return {"ok": True, "results": scored[:5]}

    async def tool_thread_resume(thread_id: int) -> Dict[str, Any]:
        from backend.db.repositories import ThreadRepository
        repo = ThreadRepository(db_path)
        thread = await repo.get_thread(thread_id)
        if thread is None:
            return {"ok": False, "error": f"Wątek {thread_id} nie istnieje."}
        await repo.update_thread(thread_id, status="active")
        orchestrator_state["active_thread_id"] = thread_id
        try:
            decisions = json.loads(thread.get("key_decisions") or "[]")
            directions = json.loads(thread.get("key_directions") or "[]")
        except (json.JSONDecodeError, TypeError):
            decisions, directions = [], []
        return {
            "ok": True,
            "thread_id": thread_id,
            "title": thread.get("title"),
            "topic_summary": thread.get("topic_summary"),
            "key_decisions": decisions,
            "key_directions": directions,
        }

    return {
        "thread_add_decision": (_TOOL_THREAD_ADD_DECISION, tool_thread_add_decision),
        "thread_add_direction": (_TOOL_THREAD_ADD_DIRECTION, tool_thread_add_direction),
        "thread_summarize": (_TOOL_THREAD_SUMMARIZE, tool_thread_summarize),
        "thread_search": (_TOOL_THREAD_SEARCH, tool_thread_search),
        "thread_resume": (_TOOL_THREAD_RESUME, tool_thread_resume),
    }


__all__ = ["make_thread_tools"]
