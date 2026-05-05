"""Heurystyka „czy wynik wyszukiwania wspiera zapisaną ligę w profilu” (T8, bez auto-archiwum)."""

from __future__ import annotations

from typing import Any, Dict

from backend.api.app_context import AppContext


def _web_search_available(registry: Any) -> bool:
    try:
        tools = registry.openai_tools()
    except Exception:
        return False
    return any(t.get("function", {}).get("name") == "web_search" for t in tools)


def _hint_search_query(game_id: str) -> str:
    g = game_id.replace("_", " ").strip()
    return f"{g} current league season patch latest official"


def _search_blob(raw: Dict[str, Any]) -> str:
    parts: list[str] = []
    if raw.get("heading"):
        parts.append(str(raw["heading"]))
    if raw.get("abstract"):
        parts.append(str(raw["abstract"]))
    rel = raw.get("related_texts") or []
    if isinstance(rel, list):
        parts.extend(str(x) for x in rel[:12])
    if raw.get("instant_answer"):
        parts.append(str(raw["instant_answer"]))
    return " ".join(parts).lower()


def league_mismatch_heuristic(profile_league: str, search_blob_lower: str) -> tuple[bool, bool]:
    """Zwraca ``(mismatch_hint, archive_suggested)`` — gdy brak ligi w profilu, oba False."""
    prof = (profile_league or "").strip().lower()
    blob = search_blob_lower.lower()
    if not prof:
        return False, False
    mismatch = prof not in blob
    return mismatch, mismatch


async def analyze_league_hint(ctx: AppContext, game_id: str) -> dict[str, Any]:
    gid = str(game_id).strip()
    if not gid:
        return {"ok": False, "error": "empty_game"}

    store = ctx.player_profile_store
    if store is None:
        return {"ok": False, "error": "no_player_profile"}

    profile = store.load()
    entry = profile.games.get(gid)
    if entry is None:
        return {"ok": False, "error": "game_not_in_profile"}

    prof_league = (entry.league or "").strip()
    mcp = ctx.config.mcp
    if not mcp.enabled or not _web_search_available(ctx.tool_registry):
        return {
            "ok": False,
            "error": "web_search_unavailable",
            "hint": "Włącz MCP i narzędzie web_search.",
        }

    query = _hint_search_query(gid)
    raw = await ctx.tool_registry.invoke("web_search", {"query": query}, system_state=None)
    if not isinstance(raw, dict):
        return {"ok": False, "error": "unexpected_search_response"}
    if not raw.get("ok"):
        return {
            "ok": False,
            "error": "search_failed",
            "detail": raw.get("error", "unknown"),
        }

    blob = _search_blob(raw)
    mismatch_hint, archive_suggested = league_mismatch_heuristic(prof_league, blob)

    return {
        "ok": True,
        "game": gid,
        "profile_league": prof_league or None,
        "query": query,
        "mismatch_hint": mismatch_hint,
        "archive_suggested": archive_suggested,
        "search_heading": raw.get("heading"),
        "search_abstract": (raw.get("abstract") or "")[:1600],
    }


__all__ = ["analyze_league_hint", "league_mismatch_heuristic", "_hint_search_query", "_search_blob"]
