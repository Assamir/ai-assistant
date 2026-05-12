"""Wspólne helpery do parsowania OpenAI-compatible chat completions.

Wyciągnięte z `llm_client.py` żeby `LlamaCppLocalClient` i `OpenRouterClient`
nie duplikowały logiki inline tool_calls parsing oraz normalizacji base URL.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Tuple


_INLINE_TOOL_TAG_CLEANUP = re.compile(
    r"</?tool_call>|<\|python_tag\|>|<\|im_end\|>|<\|tool_call_begin\|>|<\|tool_call_end\|>",
    re.IGNORECASE,
)


def _scan_json_objects(text: str) -> List[Tuple[int, int, str]]:
    """Zwraca [(start, end, raw)] dla wszystkich poprawnych obiektów JSON w tekście."""
    out: List[Tuple[int, int, str]] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        in_str = False
        esc = False
        end = -1
        for j in range(i, n):
            c = text[j]
            if esc:
                esc = False
                continue
            if c == "\\":
                esc = True
                continue
            if c == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
        if end < 0:
            break
        raw = text[i:end]
        try:
            json.loads(raw)
            out.append((i, end, raw))
        except json.JSONDecodeError:
            pass
        i = end if end > i else i + 1
    return out


def _try_parse_inline_tool_calls(content: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Wykrywa „hermes-style" tool calls wypisane w `content` (gdy backend nie wygenerował structured tool_calls).

    Łapie wzorce:
      - `<tool_call>{...}</tool_call>` (Qwen/Hermes ChatML),
      - sam JSON `{"name": "...", "arguments": {...}}` (gołe lub z artefaktami modelu),
      - `<|python_tag|>{...}` (Llama 3).

    Zwraca (cleaned_content, list[tool_call_dict]) — listę w formacie OpenAI Function Calling.
    """
    if not content or not content.strip():
        return content, []

    objects = _scan_json_objects(content)
    if not objects:
        return content, []

    parsed: List[Dict[str, Any]] = []
    spans: List[Tuple[int, int]] = []

    for start, end, raw in objects:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        name = obj.get("name")
        if not isinstance(name, str) or "arguments" not in obj:
            continue
        args = obj["arguments"]
        args_str = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
        parsed.append({
            "id": f"call_{uuid.uuid4().hex[:12]}",
            "type": "function",
            "function": {"name": name, "arguments": args_str},
        })
        spans.append((start, end))

    if not parsed:
        return content, []

    cleaned = content
    for s, e in sorted(spans, reverse=True):
        cleaned = cleaned[:s] + cleaned[e:]
    cleaned = _INLINE_TOOL_TAG_CLEANUP.sub("", cleaned).strip()
    return cleaned, parsed


def _chat_completions_base(api_base_url: str) -> str:
    """Normalizuje base URL do formatu `{base}/v1/` używanego przez httpx.AsyncClient."""
    b = api_base_url.rstrip("/")
    if b.endswith("/v1"):
        return b + "/"
    return b + "/v1/"


__all__ = [
    "_INLINE_TOOL_TAG_CLEANUP",
    "_scan_json_objects",
    "_try_parse_inline_tool_calls",
    "_chat_completions_base",
]
