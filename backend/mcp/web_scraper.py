"""web_scraper — pobranie strony HTTP (HTTPS) i ekstrakcja tekstu (trafilatura opcjonalnie)."""

from __future__ import annotations

import re
from typing import Any, Dict

import httpx

from backend.mcp.sandbox import SandboxValidator, SandboxViolation

_MAX_RESPONSE_BYTES = 2_000_000

_use_playwright_fallback = False


def configure_web_scraper(*, use_playwright_fallback: bool = False) -> None:
    global _use_playwright_fallback
    _use_playwright_fallback = bool(use_playwright_fallback)


_TOOL_WEB_SCRAPER = {
    "type": "function",
    "function": {
        "name": "web_scraper",
        "description": (
            "Pobiera publiczną stronę HTTP(S) i zwraca wyekstrahowany tekst głównej treści. "
            "Użyj do artykułów, patch notes lub stron wiki — nie do lokalnych plików (file://)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Pełny adres https:// lub http://.",
                },
            },
            "required": ["url"],
        },
    },
}


def _strip_html_fallback(html: str) -> str:
    t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    t = re.sub(r"(?is)<!--.*?-->", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _extract_main_text(html: str, page_url: str) -> tuple[str, str]:
    try:
        import trafilatura  # type: ignore[import-untyped]

        extracted = trafilatura.extract(html, url=page_url)
        if extracted and str(extracted).strip():
            return str(extracted).strip(), "trafilatura"
    except Exception:
        pass
    return _strip_html_fallback(html), "fallback"


async def _playwright_inner_text(url: str) -> str:
    from playwright.async_api import async_playwright  # type: ignore[import-untyped]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            body = await page.inner_text("body")
            return (body or "").strip()[:50_000]
        finally:
            await browser.close()


async def _http_get_html(url: str) -> str:
    headers = {"User-Agent": "Assystent-MCP-web_scraper/1.0"}
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as client:
        r = await client.get(url)
        r.raise_for_status()
        body = r.content
        if len(body) > _MAX_RESPONSE_BYTES:
            raise ValueError("odpowiedź przekracza limit rozmiaru")
        return body.decode(r.encoding or "utf-8", errors="replace")


async def tool_web_scraper(url: str | None = None, **_: Any) -> Dict[str, Any]:
    raw = url.strip() if isinstance(url, str) else ""
    if not raw:
        return {"ok": False, "error": "pusty url"}

    validator = SandboxValidator(".")
    try:
        clean_url = validator.validate_url(raw)
    except SandboxViolation as exc:
        return {"ok": False, "error": str(exc)}

    try:
        html = await _http_get_html(clean_url)
    except httpx.TimeoutException:
        return {"ok": False, "error": "timeout"}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "error": f"http {exc.response.status_code}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    text, extraction = _extract_main_text(html, clean_url)
    if (not text or len(text) < 100) and _use_playwright_fallback:
        try:
            pw_text = await _playwright_inner_text(clean_url)
            if pw_text.strip():
                text = pw_text.strip()
                extraction = "playwright"
        except Exception:
            pass
    out: Dict[str, Any] = {
        "ok": True,
        "url": clean_url,
        "text": text,
        "extraction": extraction,
    }
    if not text:
        out["note"] = "brak tekstu — możliwa strona SPA (Playwright nie jest skonfigurowany)"
    return out


__all__ = ["_TOOL_WEB_SCRAPER", "_http_get_html", "configure_web_scraper", "tool_web_scraper"]
