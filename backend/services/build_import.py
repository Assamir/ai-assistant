"""Importuje dane buildu z URL (web_scraper + LLM) i zapisuje do player_profile.yaml."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from backend.api.app_context import AppContext

_logger = logging.getLogger(__name__)

_EXTRACT_PROMPT = """\
Poniżej jest tekst strony z buildem postaci do gry. Wyciągnij z niego dane buildu.
Zwróć TYLKO JSON (bez opisu) z polami:
- "name": nazwa postaci lub buildu (string)
- "char_class": klasa postaci (string, lub "" jeśli brak)
- "build": nazwa/opis buildu (string)
- "level": poziom (int, lub 1 jeśli brak)
- "notes": krótkie notatki (string, max 200 znaków)

Tekst strony:
{text}
"""

_JSON_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def _parse_build_json(raw: str) -> Optional[Dict[str, Any]]:
    m = _JSON_RE.search(raw)
    if not m:
        return None
    try:
        data = json.loads(m.group())
    except json.JSONDecodeError:
        return None
    return {
        "name": str(data.get("name") or "").strip(),
        "char_class": str(data.get("char_class") or "").strip(),
        "build": str(data.get("build") or "").strip(),
        "level": max(1, min(100, int(data.get("level") or 1))),
        "notes": str(data.get("notes") or "").strip()[:200],
    }


async def import_build_from_url(
    ctx: "AppContext",
    game_id: str,
    url: str,
) -> Dict[str, Any]:
    """Scrape *url*, extract build data with LLM, upsert into player profile.

    Returns a dict with keys: ok, game, character (name), build, notes, error (on failure).
    """
    registry = getattr(ctx, "tool_registry", None)
    if registry is None:
        return {"ok": False, "error": "tool_registry_unavailable"}

    scrape_result: Dict[str, Any] = await registry.invoke("web_scraper", {"url": url})
    if not scrape_result.get("ok"):
        return {"ok": False, "error": scrape_result.get("error", "scrape_failed")}

    page_text: str = str(scrape_result.get("text") or "").strip()
    if not page_text:
        return {"ok": False, "error": "empty_page"}

    llm = getattr(ctx, "llm_client", None)
    if llm is None:
        return {"ok": False, "error": "llm_unavailable"}

    prompt = _EXTRACT_PROMPT.format(text=page_text[:6000])
    try:
        comp = await llm.chat_completion(
            [{"role": "user", "content": prompt}],
            max_tokens=256,
        )
    except Exception as exc:
        return {"ok": False, "error": f"llm_failed: {exc}"}

    build_data = _parse_build_json(comp.content or "")
    if not build_data:
        return {"ok": False, "error": "could_not_parse_build_data"}

    build_data["build_url"] = url

    repo = getattr(ctx, "player_profile_repo", None)
    if repo is None:
        return {"ok": False, "error": "player_profile_unavailable"}

    result = repo.upsert_character_from_build(game_id, build_data)
    if not result.get("ok"):
        return result

    return {
        "ok": True,
        "game": game_id,
        "character": build_data["name"],
        "build": build_data["build"],
        "notes": build_data["notes"],
        "url": url,
    }
