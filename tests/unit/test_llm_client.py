"""Testy LMStudioClient — mock httpx (tydzień 2 / dzień 1 planu)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx
import pytest

from backend.ai.llm_client import LMStudioClient, _chat_completions_base
from backend.config.schema import LLMConfig
from backend.core.interfaces import CircuitBreaker, CircuitBreakerOpen


def test_chat_completions_base_normalizes_v1_prefix():
    assert _chat_completions_base("http://127.0.0.1:1234") == "http://127.0.0.1:1234/v1/"
    assert _chat_completions_base("http://127.0.0.1:1234/v1") == "http://127.0.0.1:1234/v1/"
    assert _chat_completions_base("http://127.0.0.1:1234/v1/") == "http://127.0.0.1:1234/v1/"


@pytest.fixture
def llm_cfg() -> LLMConfig:
    return LLMConfig(api_base_url="http://lm.test", model_name="unit-model")


@pytest.mark.asyncio
async def test_generate_response_success(llm_cfg: LLMConfig):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url).endswith("/chat/completions")
        body = json.loads(request.content.decode())
        assert body["model"] == "unit-model"
        assert body["stream"] is False
        assert body["messages"][-1] == {"role": "user", "content": "Cześć"}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "Siema"}}]},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://lm.test/v1/") as client:
        lm = LMStudioClient(llm_cfg, http_client=client)
        text = await lm.generate_response("Cześć")
        assert text == "Siema"


@pytest.mark.asyncio
async def test_generate_response_merges_history(llm_cfg: LLMConfig):
    history = [
        {"role": "system", "content": "You are a test bot"},
        {"role": "user", "content": "Ping"},
        {"role": "assistant", "content": "Pong"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        msgs = body["messages"]
        assert msgs[:3] == history
        assert msgs[3] == {"role": "user", "content": "Next"}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "OK"}}]},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://lm.test/v1/") as client:
        lm = LMStudioClient(llm_cfg, http_client=client)
        out = await lm.generate_response("Next", history=history)
        assert out == "OK"


@pytest.mark.asyncio
async def test_chat_completion_returns_tool_calls(llm_cfg: LLMConfig):
    payload_out = {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "get_current_time", "arguments": "{}"},
                        }
                    ],
                },
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body["tools"] == [{"type": "function", "function": {"name": "get_current_time"}}]
        return httpx.Response(200, json=payload_out)

    transport = httpx.MockTransport(handler)
    tools = [{"type": "function", "function": {"name": "get_current_time"}}]
    async with httpx.AsyncClient(transport=transport, base_url="http://lm.test/v1/") as client:
        lm = LMStudioClient(llm_cfg, http_client=client)
        result = await lm.chat_completion(
            [{"role": "user", "content": "Która godzina?"}],
            tools=tools,
        )
        assert result.content == ""
        assert result.finish_reason == "tool_calls"
        assert result.tool_calls is not None
        assert result.tool_calls[0]["function"]["name"] == "get_current_time"


@pytest.mark.asyncio
async def test_stream_response_yields_delta_chunks(llm_cfg: LLMConfig):
    sse_lines = [
        'data: {"choices":[{"delta":{"content":"He"}}]}',
        'data: {"choices":[{"delta":{"content":"j"}}]}',
        "",
        "data: [DONE]",
    ]

    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        async def aiter_lines(self):
            for ln in sse_lines:
                yield ln

    class StreamCM:
        async def __aenter__(self):
            return FakeResp()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.stream = MagicMock(return_value=StreamCM())

    lm = LMStudioClient(llm_cfg, http_client=mock_client)
    parts: list[str] = []
    async for chunk in lm.stream_response("hi"):
        parts.append(chunk)

    assert "".join(parts) == "Hej"
    mock_client.stream.assert_called_once()
    call_kw = mock_client.stream.call_args
    assert call_kw[0][0] == "POST"
    assert call_kw[0][1] == "chat/completions"
    body = call_kw[1]["json"]
    assert body["stream"] is True


@pytest.mark.asyncio
async def test_stream_ignores_non_data_lines(llm_cfg: LLMConfig):
    sse_lines = [
        ": ping",
        'data: {"choices":[{"delta":{"content":"X"}}]}',
        "data: [DONE]",
    ]

    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        async def aiter_lines(self):
            for ln in sse_lines:
                yield ln

    class StreamCM:
        async def __aenter__(self):
            return FakeResp()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.stream = MagicMock(return_value=StreamCM())

    lm = LMStudioClient(llm_cfg, http_client=mock_client)
    assert [c async for c in lm.stream_response("z")] == ["X"]


@pytest.mark.asyncio
async def test_http_error_opens_circuit_breaker(llm_cfg: LLMConfig):
    cb = CircuitBreaker(failure_threshold=1, timeout_seconds=3600)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://lm.test/v1/") as client:
        lm = LMStudioClient(llm_cfg, circuit_breaker=cb, http_client=client)
        with pytest.raises(httpx.HTTPStatusError):
            await lm.generate_response("fail")

        assert cb.state == "OPEN"

        with pytest.raises(CircuitBreakerOpen):
            await lm.generate_response("blocked")


@pytest.mark.asyncio
async def test_stream_circuit_breaker_success_resets_failures(llm_cfg: LLMConfig):
    cb = CircuitBreaker(failure_threshold=2, timeout_seconds=3600)
    cb.failure_count = 1

    sse_lines = ['data: {"choices":[{"delta":{"content":"ok"}}]}', "data: [DONE]"]

    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        async def aiter_lines(self):
            for ln in sse_lines:
                yield ln

    class StreamCM:
        async def __aenter__(self):
            return FakeResp()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.stream = MagicMock(return_value=StreamCM())

    lm = LMStudioClient(llm_cfg, circuit_breaker=cb, http_client=mock_client)
    chunks = [c async for c in lm.stream_response("x")]
    assert chunks == ["ok"]
    assert cb.failure_count == 0
    assert cb.state == "CLOSED"
