"""Daily meta check — SQLite ``daily_checks`` + opcjonalny ``web_search`` (T8)."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict

from backend.api.app_context import AppContext
from backend.db.repositories import DailyCheckRepository
from backend.services.player_profile import PlayerProfileRepository

_logger = logging.getLogger(__name__)

MAX_SUMMARY_LEN = 4000


def _is_under(parent: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _sanitize_game_slug(game_id: str) -> str:
    s = "".join(c if c.isalnum() or c in "-_" else "_" for c in game_id.strip())[:48]
    return s or "game"


def write_daily_check_knowledge_note(
    content_root: Path,
    *,
    knowledge_dir: str,
    game_id: str,
    summary: str,
    query: str,
) -> str | None:
    """Zapis ``.md`` pod ``content_root`` / knowledge_dir / daily_checks / — ścieżka względna POSIX lub ``None``."""
    root = content_root.expanduser().resolve()
    kd_raw = str(knowledge_dir).strip().replace("\\", "/").strip("/")
    if not kd_raw or ".." in Path(kd_raw).parts:
        return None
    base = (root / kd_raw).resolve()
    if not _is_under(root, base):
        return None
    daily = (base / "daily_checks").resolve()
    if not _is_under(root, daily):
        return None
    daily.mkdir(parents=True, exist_ok=True)
    slug = _sanitize_game_slug(game_id)
    name = f"daily_{slug}_{int(time.time())}.md"
    path = daily / name
    meta_date = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    q_esc = query.replace("\n", " ")[:800]
    body = (
        "---\n"
        "type: daily_check\n"
        f"game: {game_id}\n"
        f"query: {q_esc}\n"
        f"generated_at: {meta_date}\n"
        "---\n\n"
        f"{summary}\n"
    )
    try:
        path.write_text(body, encoding="utf-8")
    except OSError as exc:
        _logger.debug("daily check knowledge write failed: %s", exc)
        return None
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return None


def _web_search_available(registry: Any) -> bool:
    try:
        tools = registry.openai_tools()
    except Exception:
        return False
    return any(t.get("function", {}).get("name") == "web_search" for t in tools)


def _build_search_query(game_id: str, league: str, game_version: str) -> str:
    g = game_id.replace("_", " ").strip()
    parts = [g, "game", "latest", "patch", "meta"]
    if league.strip():
        parts.insert(1, league.strip())
    if game_version.strip():
        parts.append(game_version.strip())
    return " ".join(parts)


def _summarize_search(out: Dict[str, Any]) -> tuple[str, bool]:
    if not out.get("ok"):
        err = out.get("error", "unknown")
        return f"web_search failed: {err}", False
    chunks: list[str] = []
    if out.get("heading"):
        chunks.append(str(out["heading"]))
    if out.get("abstract"):
        chunks.append(str(out["abstract"]))
    rel = out.get("related_texts") or []
    if isinstance(rel, list):
        chunks.extend(str(x) for x in rel[:4])
    text = "\n".join(chunks).strip() or "(brak treści w wyniku)"
    has = bool(out.get("abstract") or rel)
    return text[:MAX_SUMMARY_LEN], has


def touch_last_meta_check(store: PlayerProfileRepository, game_id: str) -> None:
    profile = store.load()
    entry = profile.games.get(game_id)
    if entry is None:
        return
    entry.last_meta_check = date.today()
    store.save(profile)


async def run_daily_meta_check_for_game(
    ctx: AppContext,
    game_id: str,
    *,
    force: bool = False,
    broadcast: bool = True,
) -> dict[str, Any]:
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

    mcp = ctx.config.mcp
    interval = max(1, int(mcp.daily_check_interval_hours)) * 3600
    repo = DailyCheckRepository(ctx.db_path)

    if not force:
        latest = await repo.latest_checked_at(gid)
        if latest is not None and (time.time() - float(latest)) < interval:
            return {
                "ok": True,
                "skipped": True,
                "game": gid,
                "reason": "interval_not_elapsed",
                "next_eligible_after_s": max(0, int(latest + interval - time.time())),
            }

    query = _build_search_query(gid, entry.league or "", entry.game_version or "")
    summary: str
    has_changes: bool
    if mcp.enabled and _web_search_available(ctx.tool_registry):
        raw = await ctx.tool_registry.invoke("web_search", {"query": query}, system_state=None)
        if not isinstance(raw, dict):
            summary, has_changes = f"unexpected web_search response: {type(raw).__name__}", False
        else:
            summary, has_changes = _summarize_search(raw)
    else:
        summary = "skipped web_search (mcp disabled or tool not registered)"
        has_changes = False

    root = Path(ctx.config.general.content_root).expanduser().resolve()
    knowledge_rel = write_daily_check_knowledge_note(
        root,
        knowledge_dir=ctx.config.memory.knowledge_dir,
        game_id=gid,
        summary=summary,
        query=query,
    )

    row_id = await repo.insert_row(
        gid,
        result_summary=summary,
        knowledge_file_path=knowledge_rel,
        has_changes=has_changes,
        user_notified=False,
    )

    touch_last_meta_check(store, gid)

    if knowledge_rel and ctx.config.memory.enabled and ctx.knowledge_ingester is not None:
        full = (root / knowledge_rel).resolve()
        if _is_under(root, full):
            try:
                ctx.knowledge_ingester.ingest_file(full, base=root)
            except Exception as exc:
                _logger.warning("daily check Chroma ingest failed: %s", exc)

    if broadcast:
        payload = {
            "game": gid,
            "has_changes": has_changes,
            "summary": summary[:500],
            "check_id": row_id,
        }
        if knowledge_rel:
            payload["knowledge_file_path"] = knowledge_rel
        for sid in ctx.websocket_manager.iter_session_ids():
            try:
                await ctx.websocket_manager.send_to_session(sid, "daily_check.complete", payload)
            except Exception:
                pass

    return {
        "ok": True,
        "skipped": False,
        "game": gid,
        "check_id": row_id,
        "has_changes": has_changes,
        "summary": summary[:2000],
        "knowledge_file_path": knowledge_rel,
    }


__all__ = [
    "run_daily_meta_check_for_game",
    "touch_last_meta_check",
    "write_daily_check_knowledge_note",
    "_build_search_query",
    "_summarize_search",
]
