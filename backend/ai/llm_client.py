"""Klient LM Studio — API zgodne z OpenAI (/v1/chat/completions)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from backend.config.schema import LLMConfig
from backend.core.interfaces import BaseLLMClient, CircuitBreaker, CircuitBreakerOpen


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
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "model": self._cfg.model_name,
            "messages": messages,
            "stream": stream,
            "temperature": self._cfg.temperature,
            "max_tokens": self._cfg.max_tokens,
        }
        if tools:
            body["tools"] = tools
        return body

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> ChatCompletionResult:
        """Jedno żądanie JSON (bez streamu); uwzględnia circuit breaker."""

        payload = self._payload(messages, stream=False, tools=tools)

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
        if isinstance(tool_calls, list):
            tc_list: Optional[List[Dict[str, Any]]] = tool_calls
        else:
            tc_list = None
        fr = choice.get("finish_reason")
        return ChatCompletionResult(
            content=content if isinstance(content, str) else "",
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
        payload = self._payload(messages, stream=True, tools=tools)

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
