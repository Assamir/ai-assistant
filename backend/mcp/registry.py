"""Rejestr narzędzi MCP (OpenAI-compatible) + implementacje bazowe."""

from __future__ import annotations

import asyncio
import json as _json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AbstractSet, Any, Callable, Dict, List, Mapping, MutableMapping, Optional
from zoneinfo import ZoneInfo

from backend.config.schema import MCPConfig

_TOOL_GET_TIME = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "Zwraca bieżącą datę i godzinę. Użyj przy pytaniu o czas lub dzień.",
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": (
                        "Opcjonalna strefa IANA (np. Europe/Warsaw). "
                        "Gdy pominięte — czas zegara systemowego."
                    ),
                },
            },
        },
    },
}

_TOOL_CALC = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "Wyliczenia numeryczne (sandbox asteval).",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Wyrażenie, np. 2+2, 40*1.07, (15+10)/100",
                },
            },
            "required": ["expression"],
        },
    },
}

Handler = Callable[..., Any]


def _openai_tool_name(blob: Mapping[str, Any]) -> str:
    fn = blob.get("function") if isinstance(blob, dict) else None
    if isinstance(fn, dict) and isinstance(fn.get("name"), str):
        return str(fn["name"])
    return ""


@dataclass
class ToolRegistration:
    name: str
    schema_fragment: Mapping[str, Any]
    handler: Handler


class ToolRegistry:
    """Narzędzia wywoływane z Orkiestratora przy function calling."""

    def __init__(
        self,
        *,
        db_path: Optional[str] = None,
        cache_ttl_seconds: int = 3600,
        cache_tool_names: Optional[AbstractSet[str]] = None,
        web_search_calls_per_minute: int = 10,
    ) -> None:
        self._tools: MutableMapping[str, ToolRegistration] = {}
        self._db_path = db_path
        self._cache_ttl = max(60, int(cache_ttl_seconds))
        self._cache_tools = frozenset(cache_tool_names or {"web_search", "web_scraper"})
        from backend.mcp.rate_window import AsyncRateWindow

        self._web_search_limiter = AsyncRateWindow(
            max_calls=max(1, int(web_search_calls_per_minute)),
            period_seconds=60.0,
        )
        self._cache_locks: MutableMapping[str, asyncio.Lock] = {}
        self._cache_locks_guard = asyncio.Lock()

    async def _lock_for_cache_key(self, cache_key: str) -> asyncio.Lock:
        async with self._cache_locks_guard:
            if cache_key not in self._cache_locks:
                self._cache_locks[cache_key] = asyncio.Lock()
            return self._cache_locks[cache_key]

    def register(self, name: str, schema_fragment: Mapping[str, Any], handler: Handler, *, replace: bool = False) -> None:
        if name in self._tools and not replace:
            raise ValueError(f"tool already registered: {name}")
        self._tools[name] = ToolRegistration(name=name, schema_fragment=dict(schema_fragment), handler=handler)

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def openai_tools(self) -> List[Dict[str, Any]]:
        return [reg.schema_fragment for reg in self._tools.values()]

    async def invoke(
        self,
        name: str,
        arguments: Mapping[str, Any] | None,
        *,
        system_state: Mapping[str, Any] | None = None,
    ) -> Any:
        reg = self._tools.get(name)
        if reg is None:
            raise KeyError(name)
        args = dict(arguments or {})
        if system_state is not None and system_state.get("online") is False:
            if name in ("web_search", "web_scraper"):
                return {"ok": False, "error": "offline", "detail": "Brak trybu online (wymagane połączenie)."}

        use_cache = self._db_path is not None and name in self._cache_tools
        cache_key = ""
        if use_cache:
            from backend.db.repositories import MCPCacheRepository
            from backend.mcp.cache_key import canonical_mcp_cache_key
            from backend.mcp.exceptions import RateLimitedError

            cache_key = canonical_mcp_cache_key(name, args)
            repo = MCPCacheRepository(self._db_path)
            cached = await repo.get_fresh_json(name, cache_key)
            if cached is not None:
                try:
                    return _json.loads(cached)
                except _json.JSONDecodeError:
                    pass

            lk = await self._lock_for_cache_key(cache_key)
            async with lk:
                cached2 = await repo.get_fresh_json(name, cache_key)
                if cached2 is not None:
                    try:
                        return _json.loads(cached2)
                    except _json.JSONDecodeError:
                        pass

                if name in ("web_search", "web_scraper"):
                    try:
                        await self._web_search_limiter.acquire_strict()
                    except RateLimitedError:
                        return {"ok": False, "error": "rate_limited"}

                result = reg.handler(**args)
                if asyncio.iscoroutine(result):
                    out = await result  # type: ignore[no-any-return]
                else:
                    out = result

                try:
                    dumped = out if isinstance(out, str) else _json.dumps(out, ensure_ascii=False)
                except (TypeError, ValueError):
                    dumped = ""
                if dumped:
                    await repo.put_json(name, cache_key, str(dumped), self._cache_ttl)
                return out

        if name in ("web_search", "web_scraper"):
            from backend.mcp.exceptions import RateLimitedError

            try:
                await self._web_search_limiter.acquire_strict()
            except RateLimitedError:
                return {"ok": False, "error": "rate_limited"}

        result = reg.handler(**args)
        if asyncio.iscoroutine(result):
            out = await result  # type: ignore[no-any-return]
        else:
            out = result

        if use_cache and name in self._cache_tools:
            from backend.db.repositories import MCPCacheRepository

            try:
                dumped = out if isinstance(out, str) else _json.dumps(out, ensure_ascii=False)
            except (TypeError, ValueError):
                dumped = ""
            if dumped:
                repo = MCPCacheRepository(self._db_path)
                await repo.put_json(name, cache_key, str(dumped), self._cache_ttl)

        return out

    async def invoke_openai_tool_call(
        self,
        tool_call_blob: Mapping[str, Any],
        *,
        system_state: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        fn = tool_call_blob.get("function") if isinstance(tool_call_blob, dict) else None
        name = ""
        raw_args = "{}"
        if isinstance(fn, dict):
            raw_name = fn.get("name", "")
            name = raw_name if isinstance(raw_name, str) else ""
            rv = fn.get("arguments")
            raw_args = rv if isinstance(rv, str) else _json.dumps(rv or {})

        try:
            parsed_obj = _json.loads(raw_args)
            parsed_args = parsed_obj if isinstance(parsed_obj, dict) else {}
        except _json.JSONDecodeError:
            parsed_args = {}

        out = await self.invoke(name, parsed_args, system_state=system_state)

        tc_id_raw = tool_call_blob.get("id")
        tc_id = tc_id_raw if isinstance(tc_id_raw, str) else str(tc_id_raw or "")
        payload: str
        if isinstance(out, str):
            payload = out
        else:
            payload = _json.dumps(out, ensure_ascii=False)
        return {"role": "tool", "tool_call_id": tc_id, "name": name, "content": payload}


_WEEKDAYS_PL = [
    "Poniedziałek",
    "Wtorek",
    "Środa",
    "Czwartek",
    "Piątek",
    "Sobota",
    "Niedziela",
]


def _now_iso(tz_name: Optional[str] = None) -> str:
    if tz_name:
        try:
            tz = ZoneInfo(tz_name)
            return datetime.now(tz=tz).isoformat(timespec="seconds")
        except Exception:
            dt = datetime.now(timezone.utc)
            return dt.isoformat(timespec="seconds") + f" (invalid_tz={tz_name!r})"
    return datetime.now().astimezone().isoformat(timespec="seconds")


def tool_get_current_time(**kwargs: Any) -> Dict[str, Any]:
    tz = kwargs.get("timezone")
    name = tz if isinstance(tz, str) and tz.strip() else None
    iso = _now_iso(name)
    dt: datetime
    if name:
        try:
            dt = datetime.now(ZoneInfo(name))
        except Exception:
            dt = datetime.now(timezone.utc)
    else:
        dt = datetime.now().astimezone()
    return {
        "iso_local": iso,
        "timezone": name or "local",
        "weekday_pl": _WEEKDAYS_PL[dt.weekday()],
        "hour": dt.hour,
        "date": dt.strftime("%Y-%m-%d"),
    }


def tool_calculator(expression: str) -> Dict[str, Any]:
    from asteval import Interpreter

    interp = Interpreter(use_numpy=False)
    try:
        value = interp(expression)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    err = getattr(interp, "error", None)
    if err:

        first = next(iter(err))
        detail = getattr(first, "msg", None) or repr(first)
        return {"ok": False, "error": str(detail)}
    return {"ok": True, "result": value}


def build_default_tool_registry(
    *,
    db_path: str | None = None,
    mcp_cfg: MCPConfig | None = None,
    content_root: str = ".",
) -> ToolRegistry:
    from backend.mcp.generate_document import _TOOL_GENERATE_DOCUMENT, make_tool_generate_document
    from backend.mcp.tools_extra import (
        _TOOL_DICE_ROLL,
        _TOOL_FORMAT_DURATION,
        _TOOL_RANDOM_CHOICE,
        tool_dice_roll,
        tool_format_duration,
        tool_random_choice,
    )
    from backend.mcp.web_scraper import _TOOL_WEB_SCRAPER, configure_web_scraper, tool_web_scraper
    from backend.mcp.web_search import _TOOL_WEB_SEARCH, tool_web_search

    mcp = mcp_cfg or MCPConfig()
    configure_web_scraper(use_playwright_fallback=mcp.use_playwright_fallback)
    reg = ToolRegistry(
        db_path=str(db_path) if db_path else None,
        cache_ttl_seconds=mcp.cache_ttl_seconds,
        web_search_calls_per_minute=mcp.web_search_calls_per_minute,
    )
    reg.register("get_current_time", _TOOL_GET_TIME, tool_get_current_time)
    reg.register("calculator", _TOOL_CALC, tool_calculator)
    reg.register("random_choice", _TOOL_RANDOM_CHOICE, tool_random_choice)
    reg.register("dice_roll", _TOOL_DICE_ROLL, tool_dice_roll)
    reg.register("format_duration", _TOOL_FORMAT_DURATION, tool_format_duration)
    if mcp.enabled:
        reg.register("web_search", _TOOL_WEB_SEARCH, tool_web_search)
        reg.register("web_scraper", _TOOL_WEB_SCRAPER, tool_web_scraper)
        gen_fn = make_tool_generate_document(str(content_root or "."))
        reg.register("generate_document", _TOOL_GENERATE_DOCUMENT, gen_fn)

    whitelist = frozenset(mcp.tools_enabled) if mcp.tools_enabled else None
    if whitelist:
        unwanted = [
            nm
            for nm in tuple(reg._tools.keys())
            if nm not in whitelist and nm not in ("get_current_time", "calculator")
        ]
        for nm in unwanted:
            reg.unregister(nm)
    return reg


__all__ = [
    "ToolRegistry",
    "build_default_tool_registry",
    "tool_calculator",
    "tool_get_current_time",
    "_openai_tool_name",
]
