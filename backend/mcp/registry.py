"""Rejestr narzędzi MCP (OpenAI-compatible) + implementacje bazowe."""

from __future__ import annotations

import asyncio
import json as _json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Mapping, MutableMapping, Optional
from zoneinfo import ZoneInfo

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


@dataclass
class ToolRegistration:
    name: str
    schema_fragment: Mapping[str, Any]
    handler: Handler


class ToolRegistry:
    """Narzędzia wywoływane z Orkiestratora przy function calling."""

    def __init__(self) -> None:
        self._tools: MutableMapping[str, ToolRegistration] = {}

    def register(self, name: str, schema_fragment: Mapping[str, Any], handler: Handler, *, replace: bool = False) -> None:
        if name in self._tools and not replace:
            raise ValueError(f"tool already registered: {name}")
        self._tools[name] = ToolRegistration(name=name, schema_fragment=dict(schema_fragment), handler=handler)

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def openai_tools(self) -> List[Dict[str, Any]]:
        return [reg.schema_fragment for reg in self._tools.values()]

    async def invoke(self, name: str, arguments: Mapping[str, Any] | None) -> Any:
        reg = self._tools.get(name)
        if reg is None:
            raise KeyError(name)
        args = dict(arguments or {})
        result = reg.handler(**args)
        if asyncio.iscoroutine(result):
            return await result  # type: ignore[no-any-return]
        return result

    async def invoke_openai_tool_call(self, tool_call_blob: Mapping[str, Any]) -> Dict[str, Any]:
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

        out = await self.invoke(name, parsed_args)

        tc_id_raw = tool_call_blob.get("id")
        tc_id = tc_id_raw if isinstance(tc_id_raw, str) else str(tc_id_raw or "")
        payload: str
        if isinstance(out, str):
            payload = out
        else:
            payload = _json.dumps(out, ensure_ascii=False)
        return {"role": "tool", "tool_call_id": tc_id, "name": name, "content": payload}


def _now_iso(tz_name: Optional[str] = None) -> str:
    if tz_name:
        try:
            tz = ZoneInfo(tz_name)
            return datetime.now(tz=tz).isoformat(timespec="seconds")
        except Exception:
            dt = datetime.now(timezone.utc)
            return dt.isoformat(timespec="seconds") + f" (invalid_tz={tz_name!r})"
    return datetime.now().astimezone().isoformat(timespec="seconds")


def tool_get_current_time(**kwargs: Any) -> Dict[str, str]:
    tz = kwargs.get("timezone")
    name = tz if isinstance(tz, str) and tz.strip() else None
    return {"iso_local": _now_iso(name), "timezone": name or "local"}


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


def build_default_tool_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register("get_current_time", _TOOL_GET_TIME, tool_get_current_time)
    reg.register("calculator", _TOOL_CALC, tool_calculator)
    return reg


__all__ = [
    "ToolRegistry",
    "build_default_tool_registry",
    "tool_calculator",
    "tool_get_current_time",
]
