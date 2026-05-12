"""LlamaCppLocalClient — mock Llama przez `llama_factory`. Bez realnych modeli."""

from __future__ import annotations

import json

import pytest

from backend.ai.llama_cpp_client import LlamaCppLocalClient
from backend.config.schema import LLMConfig


class FakeLlama:
    """Minimal mock spełniający kontrakt `Llama.create_chat_completion`."""

    def __init__(self, completion_response=None, stream_chunks=None):
        self._response = completion_response or {
            "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
        }
        self._stream_chunks = stream_chunks or []
        self.calls = []

    def create_chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return iter(self._stream_chunks)
        return self._response


def _cfg() -> LLMConfig:
    return LLMConfig(provider="local", temperature=0.4, max_tokens=128)


@pytest.mark.asyncio
async def test_chat_completion_basic():
    fake = FakeLlama({
        "choices": [{"message": {"role": "assistant", "content": "Cześć"}, "finish_reason": "stop"}],
    })
    client = LlamaCppLocalClient(_cfg(), model_path="/tmp/fake.gguf", llama_factory=lambda: fake)
    result = await client.chat_completion([{"role": "user", "content": "hej"}])
    assert result.content == "Cześć"
    assert result.finish_reason == "stop"
    assert fake.calls[0]["temperature"] == 0.4
    assert fake.calls[0]["max_tokens"] == 128
    assert fake.calls[0]["stream"] is False


@pytest.mark.asyncio
async def test_chat_completion_passes_tools():
    fake = FakeLlama({
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call_x",
                    "type": "function",
                    "function": {"name": "get_time", "arguments": "{}"},
                }],
            },
            "finish_reason": "tool_calls",
        }],
    })
    client = LlamaCppLocalClient(_cfg(), model_path="/tmp/fake.gguf", llama_factory=lambda: fake)
    tools = [{"type": "function", "function": {"name": "get_time", "parameters": {}}}]
    result = await client.chat_completion([{"role": "user", "content": "która godzina"}], tools=tools)

    assert fake.calls[0]["tools"] == tools
    assert fake.calls[0]["tool_choice"] == "auto"
    assert result.tool_calls is not None
    assert result.tool_calls[0]["function"]["name"] == "get_time"


@pytest.mark.asyncio
async def test_inline_tool_calls_fallback():
    """Gdy GGUF wypisze tool call w content zamiast tool_calls (Hermes/Qwen-style)."""
    raw_tool_call = json.dumps({"name": "get_time", "arguments": {"tz": "UTC"}})
    fake = FakeLlama({
        "choices": [{
            "message": {
                "role": "assistant",
                "content": f"<tool_call>{raw_tool_call}</tool_call>",
            },
            "finish_reason": "stop",
        }],
    })
    client = LlamaCppLocalClient(_cfg(), model_path="/tmp/fake.gguf", llama_factory=lambda: fake)
    result = await client.chat_completion([{"role": "user", "content": "x"}])
    assert result.tool_calls is not None
    assert result.tool_calls[0]["function"]["name"] == "get_time"
    args = json.loads(result.tool_calls[0]["function"]["arguments"])
    assert args == {"tz": "UTC"}


@pytest.mark.asyncio
async def test_lazy_init_only_once():
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return FakeLlama()

    client = LlamaCppLocalClient(_cfg(), model_path="/tmp/fake.gguf", llama_factory=factory)
    await client.chat_completion([{"role": "user", "content": "a"}])
    await client.chat_completion([{"role": "user", "content": "b"}])
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_aclose_resets_engine():
    factory_calls = {"n": 0}

    def factory():
        factory_calls["n"] += 1
        return FakeLlama()

    client = LlamaCppLocalClient(_cfg(), model_path="/tmp/fake.gguf", llama_factory=factory)
    await client.chat_completion([{"role": "user", "content": "a"}])
    await client.aclose()
    await client.chat_completion([{"role": "user", "content": "b"}])
    assert factory_calls["n"] == 2


@pytest.mark.asyncio
async def test_generate_response_builds_messages():
    fake = FakeLlama({
        "choices": [{"message": {"role": "assistant", "content": "answer"}, "finish_reason": "stop"}],
    })
    client = LlamaCppLocalClient(_cfg(), model_path="/tmp/fake.gguf", llama_factory=lambda: fake)
    history = [
        {"role": "system", "content": "you are tester"},
        {"role": "user", "content": "ping"},
        {"role": "assistant", "content": "pong"},
    ]
    out = await client.generate_response("hej", history=history)
    assert out == "answer"
    msgs = fake.calls[0]["messages"]
    assert msgs[:3] == history
    assert msgs[3] == {"role": "user", "content": "hej"}


@pytest.mark.asyncio
async def test_apply_llm_config_rebuilds_engine_on_param_change():
    factory_calls = {"n": 0}

    def factory():
        factory_calls["n"] += 1
        return FakeLlama()

    client = LlamaCppLocalClient(_cfg(), model_path="/tmp/fake.gguf", llama_factory=factory)
    await client.chat_completion([{"role": "user", "content": "a"}])
    assert factory_calls["n"] == 1

    new_cfg = LLMConfig(provider="local")
    new_cfg.local.n_gpu_layers = 5  # zmiana parametru
    await client.apply_llm_config(new_cfg)
    await client.chat_completion([{"role": "user", "content": "b"}])
    assert factory_calls["n"] == 2
