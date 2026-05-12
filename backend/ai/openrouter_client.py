"""Klient OpenRouter (cienki wrapper na LMStudioClient).

OpenRouter wystawia OpenAI-compatible API pod https://openrouter.ai/api/v1,
więc całość logiki (payload, parsowanie tool_calls, SSE streaming, fallback inline
tool_calls) re-używamy z `LMStudioClient`. Różnice: base URL, nagłówki autoryzacji
i opcjonalne nagłówki rankingowe `HTTP-Referer` / `X-Title`.
"""

from __future__ import annotations

from typing import Optional

import httpx

from backend.ai._openai_parsing import _chat_completions_base
from backend.ai.llm_client import LMStudioClient
from backend.config.schema import LLMConfig
from backend.core.interfaces import CircuitBreaker


class OpenRouterClient(LMStudioClient):
    """LLM client uderzający w OpenRouter (chmurowy fallback)."""

    def __init__(
        self,
        llm_config: LLMConfig,
        *,
        circuit_breaker: Optional[CircuitBreaker] = None,
        http_client: Optional[httpx.AsyncClient] = None,
        timeout: float = 120.0,
    ) -> None:
        or_cfg = llm_config.openrouter
        synthetic = llm_config.model_copy(update={
            "api_base_url": or_cfg.api_base_url,
            "model_name": or_cfg.model_name,
        })

        if http_client is None:
            headers = {}
            if or_cfg.api_key:
                headers["Authorization"] = f"Bearer {or_cfg.api_key}"
            if or_cfg.http_referer:
                headers["HTTP-Referer"] = or_cfg.http_referer
            if or_cfg.site_title:
                headers["X-Title"] = or_cfg.site_title
            http_client = httpx.AsyncClient(
                base_url=_chat_completions_base(or_cfg.api_base_url),
                timeout=timeout,
                headers=headers or None,
            )

        super().__init__(
            synthetic,
            circuit_breaker=circuit_breaker,
            http_client=http_client,
            timeout=timeout,
        )
        # Jesteśmy właścicielami klienta — `LMStudioClient` ustawiło to na False bo dostał http_client w param.
        # Nadpisujemy, żeby hot-reload przez apply_llm_config mógł odbudować klienta z nowymi headers.
        self._owns_client = True

    async def apply_llm_config(self, llm_config: LLMConfig) -> None:
        """Hot-reload: przeładuj base_url, model_name i nagłówki autoryzacji OpenRouter."""
        or_cfg = llm_config.openrouter
        synthetic = llm_config.model_copy(update={
            "api_base_url": or_cfg.api_base_url,
            "model_name": or_cfg.model_name,
        })
        await self._client.aclose()
        headers = {}
        if or_cfg.api_key:
            headers["Authorization"] = f"Bearer {or_cfg.api_key}"
        if or_cfg.http_referer:
            headers["HTTP-Referer"] = or_cfg.http_referer
        if or_cfg.site_title:
            headers["X-Title"] = or_cfg.site_title
        self._client = httpx.AsyncClient(
            base_url=_chat_completions_base(or_cfg.api_base_url),
            timeout=self._http_timeout,
            headers=headers or None,
        )
        self._cfg = synthetic


__all__ = ["OpenRouterClient"]
