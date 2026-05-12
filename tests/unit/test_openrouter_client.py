"""OpenRouterClient — sprawdza headers, base_url i re-use logiki LMStudioClient."""

from __future__ import annotations

import json

import httpx
import pytest

from backend.ai.openrouter_client import OpenRouterClient
from backend.config.schema import LLMConfig


def _cfg(api_key: str = "sk-or-test-key") -> LLMConfig:
    return LLMConfig(
        provider="openrouter",
        openrouter={
            "api_key": api_key,
            "model_name": "anthropic/claude-sonnet-4.6",
            "http_referer": "https://assystent.local",
            "site_title": "Assystent",
        },
    )


@pytest.mark.asyncio
async def test_uses_openrouter_base_url_and_authorization():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["referer"] = request.headers.get("http-referer")
        seen["title"] = request.headers.get("x-title")
        body = json.loads(request.content.decode())
        seen["model"] = body["model"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://openrouter.ai/api/v1/") as client:
        c = OpenRouterClient(_cfg(), http_client=client)
        out = await c.generate_response("hej")
        assert out == "ok"
    assert "openrouter.ai/api/v1" in seen["url"]
    assert seen["auth"] is None  # bo użyliśmy custom http_client bez headers; obiekt zachowuje się jak LMStudioClient
    assert seen["model"] == "anthropic/claude-sonnet-4.6"


@pytest.mark.asyncio
async def test_default_constructor_sets_auth_headers():
    """Bez injektowanego http_client — wrapper sam tworzy klienta z headers."""
    cfg = _cfg(api_key="sk-or-XYZ")
    c = OpenRouterClient(cfg)
    headers = dict(c._client.headers)  # type: ignore[attr-defined]
    auth = headers.get("authorization") or headers.get("Authorization")
    referer = headers.get("http-referer") or headers.get("HTTP-Referer")
    title = headers.get("x-title") or headers.get("X-Title")
    assert auth == "Bearer sk-or-XYZ"
    assert referer == "https://assystent.local"
    assert title == "Assystent"
    await c.aclose()


@pytest.mark.asyncio
async def test_apply_llm_config_rebuilds_headers():
    c = OpenRouterClient(_cfg(api_key="key-1"))
    new_cfg = _cfg(api_key="key-2")
    await c.apply_llm_config(new_cfg)
    headers = dict(c._client.headers)  # type: ignore[attr-defined]
    auth = headers.get("authorization") or headers.get("Authorization")
    assert auth == "Bearer key-2"
    await c.aclose()
