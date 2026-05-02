# DOK-10: MCP_TOOLS_SPEC.md — Specyfikacja MCP Tools

> **Status:** v1.0 — 2026-04-30
> **Materiały źródłowe:** PRD_02_FUNCTIONAL.md (§5), DOK-05 PROMPT_SPEC (function schemas), DECISIONS_LOG.md (DOK-10)

---

## Reguły naczelne

| # | Reguła | Materializacja |
|---|--------|---------------|
| 2 | Twardy sandbox | Wszystkie path I/O przez `SandboxValidator` |
| 3 | Lokalność danych | `web_search`/`web_scraper` aktywne tylko gdy online; brak telemetrii |
| 8 | Zero halucynacji | Tools zawsze zwracają prawdziwe dane lub błąd — nigdy placeholder |

---

## A. Sandbox Enforcement Layer

Wspólna walidacja dla wszystkich tools (wykonywana przed każdym wywołaniem):

```python
import re
from pathlib import Path

class SandboxValidator:
    def __init__(self, content_root: str):
        self._root = Path(content_root).resolve()

    def validate_path(self, path: str) -> Path:
        p = (self._root / path).resolve()
        if not str(p).startswith(str(self._root)):
            raise SandboxViolation(f"Path outside content root: {path}")
        return p

    def validate_url(self, url: str) -> str:
        if not re.match(r"^https?://", url):
            raise SandboxViolation(f"Invalid URL scheme: {url}")
        return url

    def check_online_mode(self, system_state: dict):
        if not system_state.get("online", True):
            raise OfflineModeError("Brak połączenia z internetem")

sandbox = SandboxValidator(config.general.content_root)
```

---

## B. Tool Registry

```python
from typing import Callable

_TOOLS: dict[str, "MCPTool"] = {}

def register_tool(name: str):
    def decorator(cls):
        _TOOLS[name] = cls()
        return cls
    return decorator

def get_tool_schemas() -> list[dict]:
    """Zwraca listę JSON schemas dla LLM (per turn)."""
    return [tool.schema for tool in _TOOLS.values()]

def get_tool(name: str) -> "MCPTool":
    if name not in _TOOLS:
        raise UnknownToolError(f"Tool '{name}' not registered")
    return _TOOLS[name]
```

---

## C. Tool Call Lifecycle

```
LLM response → tool_calls: [{name, arguments}]
        │
        ▼
Orchestrator:
  for each tool_call:
    1. INSERT INTO tool_calls (session_id, message_id, tool_name, input_json, turn_sequence)
    2. SandboxValidator.check()
    3. tool = ToolRegistry.get(name)
    4. result = await tool.execute(arguments, context)
    5. UPDATE tool_calls SET output_json, success, duration_ms, error_message
    6. Append tool result to messages: {role: "tool", content: result}
  → Re-query LLM with tool results
  Limit: max 5 tool calls per turn (generate_document nie liczy się)
```

---

## D. Online Mode Detection

```python
import asyncio
import socket

async def check_online() -> bool:
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, socket.setdefaulttimeout(3))
        socket.create_connection(("1.1.1.1", 53), timeout=3)
        return True
    except OSError:
        return False

async def online_monitor(system_state: SystemStateService, interval_s: int = 30):
    while True:
        online = await check_online()
        await system_state.set("online", online)
        if not online:
            await emotion_service.set("disappointed")
        await asyncio.sleep(interval_s)
```

---

## 1. Tool: `web_search`

### Sygnatura

```python
async def web_search(
    query: str,
    max_results: int = 5,
    site: str | None = None,
    freshness_days: int | None = None,
) -> list[dict]: ...
```

### Implementacja

```python
from duckduckgo_search import DDGS

@register_tool("web_search")
class WebSearchTool:
    schema = { ... }  # pełny JSON schema z DOK-05

    async def execute(self, args: dict, ctx: Context) -> list[dict]:
        sandbox.check_online_mode(ctx.system_state)
        if not await web_search_limiter.acquire():
            raise RateLimitedError()

        query = args["query"]
        max_results = args.get("max_results", 5)
        site = args.get("site")
        if site:
            query = f"site:{site} {query}"

        cache_key = make_cache_key("web_search", args)
        ttl = 86400 if _is_game_meta_query(query) else 3600

        return await mcp_cache.get_or_fetch(
            "web_search", args,
            lambda: self._ddg_search(query, max_results),
            ttl_seconds=ttl,
        )

    async def _ddg_search(self, query: str, n: int) -> list[dict]:
        loop = asyncio.get_event_loop()
        def _run():
            with DDGS() as ddg:
                return [
                    {"title": r["title"], "url": r["href"],
                     "snippet": r["body"], "published_at": r.get("published")}
                    for r in ddg.text(query, max_results=n)
                ]
        for attempt in range(3):
            try:
                return await loop.run_in_executor(None, _run)
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)

def _is_game_meta_query(query: str) -> bool:
    keywords = {"build", "meta", "patch", "tier", "guide", "wiki"}
    return any(k in query.lower() for k in keywords)
```

### Output

```json
[
  {
    "title": "Best Lightning Arrow Build 2026",
    "url": "https://maxroll.gg/poe2/lightning-arrow",
    "snippet": "Lightning Arrow Deadeye remains top clear speed...",
    "published_at": "2026-04-01"
  }
]
```

### Rate Limit / Error / Cache

- Rate: 10 req/min (token bucket)
- Network error → retry 2× (1s, 3s) → `ToolExecutionError`
- DDG blocked → fallback SearXNG jeśli `mcp.web_search_backend = searxng`
- Cache TTL: 86400s (game meta) / 3600s (inne)
- Test: 11 calls/min → 11. = `RateLimitedError` + emotion `disappointed`

---

## 2. Tool: `web_scraper`

### Sygnatura

```python
async def web_scraper(url: str) -> dict: ...
```

### Implementacja

```python
import httpx
from trafilatura import extract as trafilatura_extract

@register_tool("web_scraper")
class WebScraperTool:

    async def execute(self, args: dict, ctx: Context) -> dict:
        sandbox.check_online_mode(ctx.system_state)
        url = sandbox.validate_url(args["url"])

        return await mcp_cache.get_or_fetch(
            "web_scraper", args,
            lambda: self._scrape(url),
            ttl_seconds=604800,  # 7 dni
        )

    async def _scrape(self, url: str) -> dict:
        # Krok 1: httpx (statyczne strony)
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            content = trafilatura_extract(resp.text, include_tables=True)

        # Krok 2: Playwright fallback dla SPA (gdy treść pusta)
        if not content or len(content) < 100:
            if config.mcp.use_playwright_fallback:
                content = await self._playwright_scrape(url)

        if not content:
            raise ToolExecutionError(f"Nie udało się pobrać treści z {url}")

        return {
            "title": _extract_title(resp.text),
            "content_markdown": content,
            "fetched_at": datetime.utcnow().isoformat(),
            "url": url,
        }

    async def _playwright_scrape(self, url: str) -> str:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            content = await page.inner_text("body")
            await browser.close()
            return content[:10000]  # limit
```

### Output

```json
{
  "title": "Lightning Arrow Deadeye Build Guide",
  "content_markdown": "# Lightning Arrow Deadeye\n\nThis build focuses on...",
  "fetched_at": "2026-04-30T14:22:00",
  "url": "https://maxroll.gg/poe2/lightning-arrow"
}
```

### Cache / Error

- Cache TTL: 604800s (7 dni)
- HTTP 4xx → `ToolExecutionError` (nie retry)
- HTTP 5xx → retry 2× → `ToolExecutionError`
- Playwright fallback: `use_playwright_fallback: true` w config (domyślnie TRUE — DECISIONS_LOG DOK-10 #1)

---

## 3. Tool: `get_current_time`

### Sygnatura

```python
async def get_current_time(timezone: str = "Europe/Warsaw") -> dict: ...
```

### Implementacja

```python
from datetime import datetime
import pytz

@register_tool("get_current_time")
class GetCurrentTimeTool:

    async def execute(self, args: dict, ctx: Context) -> dict:
        tz_name = args.get("timezone", "Europe/Warsaw")
        try:
            tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            tz = pytz.timezone("Europe/Warsaw")

        now = datetime.now(tz)
        return {
            "iso": now.isoformat(),
            "weekday": now.strftime("%A"),
            "weekday_pl": _weekday_pl(now.weekday()),
            "hour": now.hour,
            "date": now.strftime("%Y-%m-%d"),
            "time_str": now.strftime("%H:%M"),
        }

WEEKDAYS_PL = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
def _weekday_pl(idx: int) -> str:
    return WEEKDAYS_PL[idx]
```

### Output

```json
{
  "iso": "2026-04-30T14:22:00+02:00",
  "weekday": "Thursday",
  "weekday_pl": "Czwartek",
  "hour": 14,
  "date": "2026-04-30",
  "time_str": "14:22"
}
```

- Cache: BRAK (zawsze świeże)
- Brak rate limitu
- Brak network (czyste `datetime.now()`)

---

## 4. Tool: `calculator`

### Sygnatura

```python
async def calculator(expression: str) -> dict: ...
```

### Implementacja

```python
import asteval

@register_tool("calculator")
class CalculatorTool:
    _aeval = asteval.Interpreter(use_numpy=False, minimal=True)
    # minimal=True: tylko matematyczne operacje, brak importu, brak exec

    async def execute(self, args: dict, ctx: Context) -> dict:
        expr = args["expression"].strip()
        if len(expr) > 500:
            raise ToolExecutionError("Expression too long (max 500 chars)")

        self._aeval.symtable.clear()  # izolacja między wywołaniami
        result = self._aeval(expr)

        if self._aeval.error:
            return {"result": None, "error": str(self._aeval.error[0].get_error())}

        return {"result": result, "error": None}
```

### Output

```json
{ "result": 608.175, "error": null }
{ "result": null, "error": "ZeroDivisionError: division by zero" }
```

- Cache: BRAK
- Sandbox: `asteval minimal` — brak `import`, `exec`, `eval`, filesystem
- Dozwolone: `sum`, `min`, `max`, `abs`, `round`, `sqrt` + operatory arytmetyczne

---

## 5. Tool: `generate_document`

### Sygnatura

```python
async def generate_document(
    topic: str,
    format: Literal["md", "html"],
    content: str,
    filename_hint: str = "",
) -> dict: ...
```

### Implementacja

```python
from datetime import datetime
import re

@register_tool("generate_document")
class GenerateDocumentTool:

    async def execute(self, args: dict, ctx: Context) -> dict:
        topic = args["topic"][:60]
        fmt = args["format"]
        content = args["content"]
        hint = args.get("filename_hint", "")

        # Format nazwy: {type}_{slug}_{YYYY-MM-DD-HH.MM}.{ext}
        slug = hint if hint else re.sub(r"[^\w]", "_", topic.lower())[:40]
        timestamp = datetime.now().strftime("%Y-%m-%d-%H.%M")
        filename = f"document_{slug}_{timestamp}.{fmt}"

        docs_dir = sandbox.validate_path("documents")
        docs_dir.mkdir(exist_ok=True)
        filepath = docs_dir / filename

        if fmt == "html":
            full_content = HTML_TEMPLATE.replace("{{CONTENT}}", content)
            full_content = full_content.replace("{{TITLE}}", topic)
        else:
            full_content = content

        filepath.write_text(full_content, encoding="utf-8")

        return {
            "file_path": str(filepath),
            "filename": filename,
            "file_size": filepath.stat().st_size,
            "format": fmt,
        }
```

### HTML Template

```python
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<title>{{TITLE}}</title>
<style>
  body { background:#1a1a2e; color:#e0e0e0; font-family:system-ui,sans-serif;
         max-width:900px; margin:0 auto; padding:2rem; line-height:1.6; }
  h1,h2,h3 { color:#a78bfa; }
  table { border-collapse:collapse; width:100%; margin:1rem 0; }
  th,td { border:1px solid #3f3f5f; padding:0.5rem 1rem; text-align:left; }
  th { background:#2d2d4e; }
  code { background:#2d2d4e; padding:0.1em 0.4em; border-radius:4px; }
  @media print { body { background:white; color:black; } }
</style>
<!-- Mermaid.js (optional diagrams) -->
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"
        onerror="console.warn('Mermaid offline — diagrams show as code')"></script>
</head>
<body>
{{CONTENT}}
</body>
</html>"""
```

### Output

```json
{
  "file_path": "c:\\ai\\asystent\\documents\\document_la_vs_ts_2026-04-30-14.22.html",
  "filename": "document_la_vs_ts_2026-04-30-14.22.html",
  "file_size": 8192,
  "format": "html"
}
```

- Nazwy unikalne (timestamp) — NIGDY overwrite (DECISIONS_LOG DOK-10 #3)
- Nie liczy się do limitu 5 tool calls per turn
- Sandbox: zapisuje TYLKO do `{content_root}/documents/`

---

## 6. Tool: `screen_capture`

### Sygnatura

```python
async def screen_capture(
    focus_cursor: bool = False,
    prompt: str = "",
) -> dict: ...
```

### Implementacja

```python
@register_tool("screen_capture")
class ScreenCaptureTool:

    async def execute(self, args: dict, ctx: Context) -> dict:
        focus = args.get("focus_cursor", False)
        prompt = args.get("prompt", "Opisz co widzisz na ekranie.")

        frame = await ctx.screen_capture_service.capture()
        if frame is None:
            raise ToolExecutionError("Nie mogę uzyskać dostępu do ekranu")

        # Kursor crop jeśli focus_cursor
        crop_frame = frame
        if focus:
            import pyautogui
            cx, cy = pyautogui.position()
            h, w = frame.shape[:2]
            x1, y1 = max(0, cx-300), max(0, cy-200)
            x2, y2 = min(w, cx+300), min(h, cy+200)
            crop_frame = frame[y1:y2, x1:x2]

        # VLM analysis
        vlm_prompt = prompt or "Opisz co widzisz na tym ekranie."
        description = await ctx.vlm.describe(frame, vlm_prompt)

        # OCR jeśli potrzebne
        ocr_text = ""
        if should_run_ocr(description) or focus:
            ocr_text = await run_ocr(crop_frame)

        return {
            "description": description,
            "ocr_text": ocr_text,
            "cursor_focused": focus,
        }
```

### Output

```json
{
  "description": "Gracz patrzy na tooltip itemu: łuk z affixami lightning damage.",
  "ocr_text": "Adds 45-78 Lightning Damage\nTier 2\nRequires Level 60",
  "cursor_focused": true
}
```

- Brak cache (real-time)
- Jeden call per turn (patrz anty-wzorce DOK-05)
- Screenshot in-memory, brak zapisu (chyba że debug mode)

---

## E. Tool Call Logging

Każde wywołanie → `tool_calls` table:

```sql
INSERT INTO tool_calls
  (session_id, message_id, tool_name, input_json, turn_sequence, started_at)
VALUES (?, ?, ?, ?, ?, unixepoch());

-- po wykonaniu:
UPDATE tool_calls
SET output_json = ?, success = ?, duration_ms = ?, error_message = ?
WHERE id = ?;
```

---

## F. Testy per Tool

| Tool | Test ID | Scenario | Expected |
|------|---------|----------|---------|
| web_search | MCP-T-01 | Query "PoE2 LA build" | 5 wyników, cache write |
| web_search | MCP-T-02 | Identyczny query < 24h | Cache hit, brak network |
| web_search | MCP-T-03 | 11. call/min | `RateLimitedError` |
| web_search | MCP-T-04 | `online=false` | `OfflineModeError` |
| web_scraper | MCP-T-05 | Static HTML URL | Treść wyekstrahowana |
| web_scraper | MCP-T-06 | SPA URL (pusta treść) | Playwright fallback |
| get_current_time | MCP-T-07 | Call | iso, weekday_pl, hour |
| calculator | MCP-T-08 | "(450+78)*1.35" | 713.16 |
| calculator | MCP-T-09 | "import os; os.listdir('.')" | `error: NameError` |
| generate_document | MCP-T-10 | format="html", content="..." | Plik zapisany w documents/ |
| generate_document | MCP-T-11 | Drugi call z tym samym hint | Nowa nazwa (timestamp różny) |
| screen_capture | MCP-T-12 | focus_cursor=True | description + ocr_text |
| sandbox | MCP-T-13 | path="../../../etc/passwd" | `SandboxViolation` |

---

*Dokument: DOK-10 MCP_TOOLS_SPEC.md v1.0 — 2026-04-30*
*Następny: DOK-11 MEMORY_SPEC.md*
