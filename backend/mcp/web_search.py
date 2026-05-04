"""web_search — DuckDuckGo Instant Answer API (JSON) + limity z ToolRegistry."""

from __future__ import annotations

from typing import Any, Dict

import httpx

_DDG_URL = "https://api.duckduckgo.com/"


async def _ddg_fetch(params: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=12.0) as client:
        r = await client.get(_DDG_URL, params=params)
        r.raise_for_status()
        return r.json()


_TOOL_WEB_SEARCH = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Wyszukiwanie w internecie (DuckDuckGo — streszczenie + powiązane tematy). "
            "Użyj do faktów, patch notes, nazw lokacji lub buildów nieobecnych w lokalnym kontekście."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Zapytanie po polsku lub angielsku.",
                },
            },
            "required": ["query"],
        },
    },
}


async def tool_web_search(query: str | None = None, **_: Any) -> Dict[str, Any]:
    q = query.strip() if isinstance(query, str) else ""
    if not q:
        return {"ok": False, "error": "pusty query"}
    params = {"q": q, "format": "json", "no_redirect": "1", "no_html": "1"}
    try:
        body = await _ddg_fetch(params)
    except httpx.TimeoutException:
        return {"ok": False, "error": "timeout"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    topics: list[str] = []
    for t in body.get("RelatedTopics") or []:
        if isinstance(t, dict) and "Text" in t:
            topics.append(str(t["Text"]))
        elif isinstance(t, dict) and "Topics" in t:
            for sub in t["Topics"]:
                if isinstance(sub, dict) and "Text" in sub:
                    topics.append(str(sub["Text"]))
    abstract = body.get("AbstractText") or ""
    heading = body.get("Heading") or ""
    url_out = body.get("AbstractURL") or ""
    return {
        "ok": True,
        "query": q,
        "abstract": abstract,
        "heading": heading,
        "abstract_url": url_out,
        "related_texts": topics[:8],
        "instant_answer": body.get("Answer") or "",
    }


__all__ = ["tool_web_search", "_TOOL_WEB_SEARCH", "_ddg_fetch"]
