"""web_search — wyniki tekstowe (ddgs / SERP) + opcjonalnie Instant Answer API DuckDuckGo."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import httpx

_DDG_INSTANT_URL = "https://api.duckduckgo.com/"


def _sync_ddgs_text_results(query: str, max_results: int = 10) -> List[Dict[str, str]]:
    """Synchroniczne wyszukiwanie tekstowe przez pakiet `ddgs` (meta‑SERP)."""
    try:
        from ddgs import DDGS
    except ImportError:
        return []

    rows: List[Dict[str, str]] = []
    try:
        ddgs = DDGS(timeout=15)
        for item in ddgs.text(query, max_results=max_results):
            if not isinstance(item, dict):
                continue
            href = str(item.get("href") or item.get("url") or "")
            rows.append(
                {
                    "title": str(item.get("title") or ""),
                    "url": href,
                    "snippet": str(item.get("body") or ""),
                }
            )
    except Exception:
        return rows
    return rows


async def _ddg_instant_fetch(params: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=12.0) as client:
        r = await client.get(_DDG_INSTANT_URL, params=params)
        r.raise_for_status()
        return r.json()


_TOOL_WEB_SEARCH = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Wyszukiwanie w internecie (lista stron ze snippetami + ewentualne streszczenie DDG). "
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


def _related_topics_from_instant(body: Dict[str, Any]) -> List[str]:
    topics: list[str] = []
    for t in body.get("RelatedTopics") or []:
        if isinstance(t, dict) and "Text" in t:
            topics.append(str(t["Text"]))
        elif isinstance(t, dict) and "Topics" in t:
            for sub in t["Topics"]:
                if isinstance(sub, dict) and "Text" in sub:
                    topics.append(str(sub["Text"]))
    return topics


_MAX_RESULTS = 5
_MAX_RELATED = 3
_MAX_SNIPPET = 200
_MAX_TITLE = 100
_MAX_ABSTRACT = 400


def _trim(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _compact_results(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Top N wyników z przyciętymi polami — chroni LLM przed nadmiarem kontekstu."""
    out: list[Dict[str, str]] = []
    for r in rows[:_MAX_RESULTS]:
        out.append({
            "title": _trim(r.get("title") or "", _MAX_TITLE),
            "url": (r.get("url") or "").strip(),
            "snippet": _trim(r.get("snippet") or "", _MAX_SNIPPET),
        })
    return out


def _format_ddgs_lines(rows: List[Dict[str, str]]) -> List[str]:
    lines: list[str] = []
    for r in rows[:_MAX_RESULTS]:
        title = _trim(r.get("title") or "", _MAX_TITLE)
        snip = _trim(r.get("snippet") or "", _MAX_SNIPPET)
        url = (r.get("url") or "").strip()
        head = f"{title}: {snip}".strip(": ").strip() if title else snip
        if not head and url:
            head = url
        if url and url not in head:
            head = f"{head} | {url}" if head else url
        if head:
            lines.append(head)
    return lines


async def tool_web_search(query: str | None = None, **_: Any) -> Dict[str, Any]:
    import time

    from backend.mcp.network_audit import log_mcp_network_call

    q = query.strip() if isinstance(query, str) else ""
    audit_args: Dict[str, Any] = {"query": q}
    t0 = time.perf_counter()

    def _audit_done(out: Dict[str, Any]) -> Dict[str, Any]:
        dt = int((time.perf_counter() - t0) * 1000)
        ok = bool(out.get("ok"))
        log_mcp_network_call("web_search", arguments=audit_args, duration_ms=dt, success=ok)
        return out

    if not q:
        return _audit_done({"ok": False, "error": "pusty query"})

    instant_params = {"q": q, "format": "json", "no_redirect": "1", "no_html": "1"}

    async def _safe_instant() -> Dict[str, Any]:
        try:
            return await _ddg_instant_fetch(instant_params)
        except (httpx.TimeoutException, httpx.HTTPError, Exception):
            return {}

    body, ddgs_rows = await asyncio.gather(
        _safe_instant(),
        asyncio.to_thread(_sync_ddgs_text_results, q, 10),
    )

    topics = _related_topics_from_instant(body)
    ddgs_lines = _format_ddgs_lines(ddgs_rows)
    related_texts = (ddgs_lines + topics)[:_MAX_RELATED]

    abstract = _trim(str(body.get("AbstractText") or ""), _MAX_ABSTRACT)
    heading = _trim(str(body.get("Heading") or ""), _MAX_TITLE)
    url_out = str(body.get("AbstractURL") or "")
    instant_answer = _trim(str(body.get("Answer") or ""), _MAX_ABSTRACT)

    if ddgs_rows:
        if not abstract.strip():
            abstract = _trim(ddgs_rows[0].get("snippet") or ddgs_rows[0].get("title") or "", _MAX_ABSTRACT)
        if not heading.strip():
            heading = _trim(ddgs_rows[0].get("title") or "", _MAX_TITLE)
        if not url_out.strip():
            url_out = ddgs_rows[0].get("url") or url_out

    compact = _compact_results(ddgs_rows)

    has_signal = bool(
        abstract.strip()
        or heading.strip()
        or url_out.strip()
        or related_texts
        or instant_answer.strip()
        or compact
    )

    return _audit_done(
        {
            "ok": has_signal,
            "query": q,
            "abstract": abstract,
            "heading": heading,
            "abstract_url": url_out,
            "related_texts": related_texts,
            "instant_answer": instant_answer,
            "results": compact,
            **({"error": "brak wyników — spróbuj krótszego zapytania lub języka angielskiego"} if not has_signal else {}),
        }
    )


__all__ = ["tool_web_search", "_TOOL_WEB_SEARCH", "_ddg_instant_fetch", "_sync_ddgs_text_results"]
