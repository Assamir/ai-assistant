"""Klient LM Studio — API zgodne z OpenAI (/v1/chat/completions)."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import httpx

from backend.config.schema import LLMConfig
from backend.core.interfaces import BaseLLMClient, CircuitBreaker, CircuitBreakerOpen


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
    """Wykrywa „hermes-style" tool calls wypisane w `content` (gdy LM Studio nie wygenerował structured tool_calls).

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
    b = api_base_url.rstrip("/")
    if b.endswith("/v1"):
        return b + "/"
    return b + "/v1/"


@dataclass
class ChatCompletionResult:
    """Wynik pojedynczego żądania chat completions (bez streamingu)."""

    content: str
    finish_reason: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    raw: Optional[Dict[str, Any]] = None


class LMStudioClient(BaseLLMClient):
    """HTTP klient async pod LM Studio / OpenAI-compatible chat completions."""

    _PATH = "chat/completions"

    def __init__(
        self,
        llm_config: LLMConfig,
        *,
        circuit_breaker: Optional[CircuitBreaker] = None,
        http_client: Optional[httpx.AsyncClient] = None,
        timeout: float = 120.0,
    ) -> None:
        self._cfg = llm_config
        self._breaker = circuit_breaker
        self._owns_client = http_client is None
        self._http_timeout = timeout
        base = _chat_completions_base(llm_config.api_base_url)
        self._client = http_client or httpx.AsyncClient(
            base_url=base,
            timeout=timeout,
        )

    async def apply_llm_config(self, llm_config: LLMConfig) -> None:
        """Hot-reload / runtime: nowe ustawienia LLM; odtwarza klienta HTTP gdy jesteśmy jego właścicielem."""
        self._cfg = llm_config
        if not self._owns_client:
            return
        base = _chat_completions_base(llm_config.api_base_url)
        await self._client.aclose()
        self._client = httpx.AsyncClient(base_url=base, timeout=self._http_timeout)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _messages(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        msgs: List[Dict[str, Any]] = []
        if history:
            for item in history:
                role = item.get("role")
                content = item.get("content")
                if isinstance(role, str) and content is not None:
                    msgs.append({"role": role, "content": content})
        msgs.append({"role": "user", "content": prompt})
        return msgs

    def _payload(
        self,
        messages: List[Dict[str, Any]],
        *,
        stream: bool,
        tools: Optional[List[Dict[str, Any]]],
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "model": self._cfg.model_name,
            "messages": messages,
            "stream": stream,
            "temperature": self._cfg.temperature,
            "max_tokens": int(max_tokens) if max_tokens is not None else self._cfg.max_tokens,
        }
        if tools:
            body["tools"] = tools
        return body

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
    ) -> ChatCompletionResult:
        """Jedno żądanie JSON (bez streamu); uwzględnia circuit breaker."""

        payload = self._payload(messages, stream=False, tools=tools, max_tokens=max_tokens)

        async def do_post() -> Dict[str, Any]:
            r = await self._client.post(self._PATH, json=payload)
            r.raise_for_status()
            return r.json()

        if self._breaker:
            data = await self._breaker.call_async(do_post)
        else:
            data = await do_post()

        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        content = msg.get("content") or ""
        tool_calls = msg.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            tc_list: Optional[List[Dict[str, Any]]] = tool_calls
        else:
            tc_list = None

        content_str = content if isinstance(content, str) else ""
        # Fallback: część modeli (Qwen/Hermes w LM Studio, Llama 3) wypisuje tool calls jako
        # tekst w `content` zamiast structured `tool_calls`. Parsujemy je ręcznie.
        if tc_list is None and content_str:
            cleaned, parsed = _try_parse_inline_tool_calls(content_str)
            if parsed:
                tc_list = parsed
                content_str = cleaned

        fr = choice.get("finish_reason")
        return ChatCompletionResult(
            content=content_str,
            finish_reason=fr if isinstance(fr, str) else None,
            tool_calls=tc_list,
            raw=data,
        )

    async def generate_response(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        messages = self._messages(prompt, history)
        result = await self.chat_completion(messages, tools=tools)
        return result.content

    async def stream_response(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[str]:
        messages = self._messages(prompt, history)
        payload = self._payload(messages, stream=True, tools=tools, max_tokens=None)

        if self._breaker:
            self._breaker.check_allow()

        try:
            async with self._client.stream(
                "POST",
                self._PATH,
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for piece in self._iter_sse_content_chunks(resp):
                    yield piece
            if self._breaker:
                self._breaker.mark_success()
        except CircuitBreakerOpen:
            raise
        except Exception:
            if self._breaker:
                self._breaker.mark_failure()
            raise

    async def _iter_sse_content_chunks(self, resp: httpx.Response) -> AsyncIterator[str]:
        async for line in resp.aiter_lines():
            if line.startswith(":"):
                continue
            if not line.startswith("data:"):
                continue
            payload = line[len("data:") :].strip()
            if payload == "[DONE]":
                break
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                continue
            choices = data.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            chunk = delta.get("content")
            if chunk:
                yield chunk


__all__ = ["LMStudioClient", "ChatCompletionResult", "_chat_completions_base"]
