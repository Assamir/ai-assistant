"""Narzędzia MCP do planowania agentowego (System A)."""

from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, List, MutableMapping, Optional

_TOOL_PLAN_CREATE = {
    "type": "function",
    "function": {
        "name": "plan_create",
        "description": (
            "Tworzy plan kroków do realizacji złożonego celu. "
            "Wywołaj JAKO PIERWSZY gdy masz złożone zadanie wymagające kilku etapów. "
            "Każdy krok powinien być konkretnym, wykonalnym działaniem."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "Cel do osiągnięcia (jedno zdanie).",
                },
                "steps": {
                    "type": "array",
                    "description": "Lista kroków do wykonania (2-6 kroków).",
                    "items": {"type": "string"},
                },
            },
            "required": ["goal", "steps"],
        },
    },
}

_TOOL_PLAN_GET = {
    "type": "function",
    "function": {
        "name": "plan_get",
        "description": "Zwraca aktualny stan planu z postępem kroków.",
        "parameters": {"type": "object", "properties": {}},
    },
}

_TOOL_TASK_START = {
    "type": "function",
    "function": {
        "name": "task_start",
        "description": "Oznacza krok planu jako aktualnie realizowany.",
        "parameters": {
            "type": "object",
            "properties": {
                "step_index": {
                    "type": "integer",
                    "description": "Indeks kroku (0-based).",
                },
            },
            "required": ["step_index"],
        },
    },
}

_TOOL_TASK_DONE = {
    "type": "function",
    "function": {
        "name": "task_done",
        "description": "Zamyka krok planu z wynikiem.",
        "parameters": {
            "type": "object",
            "properties": {
                "step_index": {
                    "type": "integer",
                    "description": "Indeks zakończonego kroku (0-based).",
                },
                "result": {
                    "type": "string",
                    "description": "Krótkie podsumowanie wyniku (1-2 zdania).",
                },
            },
            "required": ["step_index", "result"],
        },
    },
}

_TOOL_TASK_REVISE = {
    "type": "function",
    "function": {
        "name": "task_revise",
        "description": (
            "Rewiduje plan — zmienia lub dodaje kroki na podstawie nowych informacji. "
            "Wywołaj gdy odkryjesz że plan wymaga zmiany w trakcie realizacji."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Powód rewizji planu.",
                },
                "new_steps": {
                    "type": "array",
                    "description": "Nowe/zaktualizowane kroki od bieżącego punktu.",
                    "items": {"type": "string"},
                },
            },
            "required": ["reason", "new_steps"],
        },
    },
}

_TOOL_WORK_EVALUATE = {
    "type": "function",
    "function": {
        "name": "work_evaluate",
        "description": (
            "Ocenia jakość wykonanej pracy. Wywołaj po zakończeniu wszystkich kroków. "
            "Zwróć szczerą ocenę 0.0-1.0 (0=kompletna porażka, 1=cel w pełni osiągnięty)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "Cel który miał być osiągnięty.",
                },
                "summary": {
                    "type": "string",
                    "description": "Podsumowanie co zostało zrobione.",
                },
                "quality_score": {
                    "type": "number",
                    "description": "Ocena jakości 0.0-1.0.",
                },
                "issues": {
                    "type": "string",
                    "description": "Opcjonalnie: co jest niekompletne lub błędne.",
                },
            },
            "required": ["goal", "summary", "quality_score"],
        },
    },
}

_TOOL_NOTE_SAVE = {
    "type": "function",
    "function": {
        "name": "note_save",
        "description": (
            "Zapisuje krótką obserwację lub fakt zebrany podczas realizacji planu. "
            "Notatki są dostępne przez notes_get w bieżącej sesji."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Treść notatki (1-3 zdania).",
                },
            },
            "required": ["content"],
        },
    },
}

_TOOL_NOTES_GET = {
    "type": "function",
    "function": {
        "name": "notes_get",
        "description": "Zwraca notatki zebrane podczas bieżącej sesji / planu.",
        "parameters": {"type": "object", "properties": {}},
    },
}


def make_agent_tools(
    db_path: Optional[str],
    orchestrator_state: MutableMapping[str, Any],
) -> Dict[str, tuple[Dict[str, Any], Callable[..., Any]]]:
    """Zwraca słownik {nazwa: (schema, handler)} dla narzędzi agentowych."""

    def _plan(state: MutableMapping[str, Any]) -> List[Dict[str, Any]]:
        return state.setdefault("agent_plan", [])  # type: ignore[return-value]

    async def tool_plan_create(goal: str, steps: List[str]) -> Dict[str, Any]:
        plan: List[Dict[str, Any]] = []
        for i, step in enumerate(steps[:8]):
            plan.append({
                "index": i,
                "description": str(step).strip(),
                "status": "pending",
                "result": None,
                "started_at": None,
                "done_at": None,
            })
        orchestrator_state["agent_plan"] = plan
        orchestrator_state["agent_goal"] = str(goal).strip()
        orchestrator_state["agent_plan_created_at"] = int(time.time())
        orchestrator_state["agent_quality_score"] = None

        if db_path:
            try:
                from backend.db.repositories import AgentTaskRepository
                session_id = orchestrator_state.get("db_session_id")
                thread_id = orchestrator_state.get("active_thread_id")
                repo = AgentTaskRepository(db_path)
                task_ids = []
                for item in plan:
                    tid = await repo.create_task(
                        session_id=session_id,
                        thread_id=thread_id,
                        goal_text=str(goal).strip(),
                        step_index=item["index"],
                        total_steps=len(plan),
                        description=item["description"],
                    )
                    task_ids.append(tid)
                orchestrator_state["agent_task_ids"] = task_ids
            except Exception:
                pass

        return {
            "ok": True,
            "goal": goal,
            "steps": [{"index": s["index"], "description": s["description"]} for s in plan],
            "total": len(plan),
        }

    async def tool_plan_get() -> Dict[str, Any]:
        plan = _plan(orchestrator_state)
        goal = orchestrator_state.get("agent_goal", "")
        return {
            "ok": True,
            "goal": goal,
            "steps": [
                {
                    "index": s["index"],
                    "description": s["description"],
                    "status": s["status"],
                    "result": s.get("result"),
                }
                for s in plan
            ],
            "done_count": sum(1 for s in plan if s["status"] in ("done", "skipped")),
            "total": len(plan),
        }

    async def tool_task_start(step_index: int) -> Dict[str, Any]:
        plan = _plan(orchestrator_state)
        idx = int(step_index)
        if not (0 <= idx < len(plan)):
            return {"ok": False, "error": f"Krok {idx} nie istnieje."}
        plan[idx]["status"] = "in_progress"
        plan[idx]["started_at"] = int(time.time())
        return {"ok": True, "step_index": idx, "description": plan[idx]["description"]}

    async def tool_task_done(step_index: int, result: str) -> Dict[str, Any]:
        plan = _plan(orchestrator_state)
        idx = int(step_index)
        if not (0 <= idx < len(plan)):
            return {"ok": False, "error": f"Krok {idx} nie istnieje."}
        plan[idx]["status"] = "done"
        plan[idx]["result"] = str(result).strip()
        plan[idx]["done_at"] = int(time.time())

        if db_path:
            try:
                task_ids = orchestrator_state.get("agent_task_ids", [])
                if idx < len(task_ids):
                    from backend.db.repositories import AgentTaskRepository
                    await AgentTaskRepository(db_path).update_task(
                        task_ids[idx],
                        status="done",
                        result_summary=str(result).strip()[:500],
                    )
            except Exception:
                pass

        return {"ok": True, "step_index": idx, "result": result}

    async def tool_task_revise(reason: str, new_steps: List[str]) -> Dict[str, Any]:
        plan = _plan(orchestrator_state)
        done_steps = [s for s in plan if s["status"] in ("done", "skipped")]
        next_index = len(done_steps)
        for i, step in enumerate(new_steps[:6]):
            new_step: Dict[str, Any] = {
                "index": next_index + i,
                "description": str(step).strip(),
                "status": "pending",
                "result": None,
                "started_at": None,
                "done_at": None,
            }
            if next_index + i < len(plan):
                plan[next_index + i] = new_step
            else:
                plan.append(new_step)
        del plan[next_index + len(new_steps):]
        orchestrator_state["agent_plan"] = plan
        return {
            "ok": True,
            "reason": reason,
            "revised_from_step": next_index,
            "new_total": len(plan),
        }

    async def tool_work_evaluate(
        goal: str,
        summary: str,
        quality_score: float,
        issues: str = "",
    ) -> Dict[str, Any]:
        score = float(quality_score)
        score = max(0.0, min(1.0, score))
        orchestrator_state["agent_quality_score"] = score
        orchestrator_state["agent_evaluation_summary"] = str(summary).strip()

        if db_path:
            try:
                session_id = orchestrator_state.get("db_session_id")
                thread_id = orchestrator_state.get("active_thread_id")
                task_ids = orchestrator_state.get("agent_task_ids", [])
                if task_ids:
                    from backend.db.repositories import AgentTaskRepository
                    await AgentTaskRepository(db_path).update_task(
                        task_ids[0],
                        quality_score=score,
                    )
            except Exception:
                pass

        return {
            "ok": True,
            "quality_score": score,
            "verdict": "cel osiągnięty" if score >= 0.7 else "wynik niepełny",
            "summary": summary,
            "issues": issues,
        }

    async def tool_note_save(content: str) -> Dict[str, Any]:
        notes = orchestrator_state.setdefault("agent_notes_mem", [])
        note = {
            "content": str(content).strip(),
            "created_at": int(time.time()),
        }
        notes.append(note)

        if db_path:
            try:
                from backend.db.repositories import AgentNoteRepository
                session_id = orchestrator_state.get("db_session_id")
                thread_id = orchestrator_state.get("active_thread_id")
                task_ids = orchestrator_state.get("agent_task_ids", [])
                task_id = task_ids[0] if task_ids else None
                await AgentNoteRepository(db_path).save_note(
                    session_id=session_id,
                    task_id=task_id,
                    thread_id=thread_id,
                    content=str(content).strip(),
                )
            except Exception:
                pass

        return {"ok": True, "content": content}

    async def tool_notes_get() -> Dict[str, Any]:
        notes = orchestrator_state.get("agent_notes_mem", [])
        return {
            "ok": True,
            "notes": [n["content"] for n in notes[-10:]],
            "count": len(notes),
        }

    return {
        "plan_create": (_TOOL_PLAN_CREATE, tool_plan_create),
        "plan_get": (_TOOL_PLAN_GET, tool_plan_get),
        "task_start": (_TOOL_TASK_START, tool_task_start),
        "task_done": (_TOOL_TASK_DONE, tool_task_done),
        "task_revise": (_TOOL_TASK_REVISE, tool_task_revise),
        "work_evaluate": (_TOOL_WORK_EVALUATE, tool_work_evaluate),
        "note_save": (_TOOL_NOTE_SAVE, tool_note_save),
        "notes_get": (_TOOL_NOTES_GET, tool_notes_get),
    }


__all__ = ["make_agent_tools"]
