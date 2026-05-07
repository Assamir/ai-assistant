"""ai_runtime.mirror_tool_results_as_user — echo wyniku narzędzia jako wiadomość user (LM Studio FC)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.ai.llm_client import ChatCompletionResult
from backend.config.schema import AIControlConfig, ConfigSchema, LLMConfig
from backend.core.command_matching import CommandMatcher
from backend.core.orchestrator import ConversationOrchestrator
from backend.core.persona_loader import PersonaLoader
from backend.core.prompt_builder import PromptBuilder
from backend.mcp.registry import build_default_tool_registry


class _RecordingLLM:
    def __init__(self) -> None:
        self.calls: list[list[dict]] = []
        self._n = 0

    async def chat_completion(self, messages, *, tools=None, max_tokens=None):
        self.calls.append([dict(m) for m in messages])
        if self._n == 0:
            self._n += 1
            return ChatCompletionResult(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "type": "function",
                        "function": {"name": "get_current_time", "arguments": "{}"},
                    }
                ],
            )
        return ChatCompletionResult(content="Odpowiedź po narzędziu.", tool_calls=None)

    async def aclose(self) -> None:
        pass


def _orch(tmp_path: Path, *, mirror: bool) -> tuple[ConversationOrchestrator, _RecordingLLM]:
    personas_dir = tmp_path / "personas"
    personas_dir.mkdir()
    stub = _RecordingLLM()
    cfg = ConfigSchema(
        llm=LLMConfig(api_base_url="http://stub/", model_name="stub"),
        ai_runtime=AIControlConfig(
            max_context_tokens=2048,
            max_tool_calls_per_turn=3,
            mirror_tool_results_as_user=mirror,
        ),
    )
    orch = ConversationOrchestrator(
        configuration=cfg,
        lm_client=stub,  # type: ignore[arg-type]
        prompt_builder=PromptBuilder(max_context_tokens=2048),
        persona_loader=PersonaLoader(personas_dir),
        command_matcher=CommandMatcher(fuzzy=True),
        tool_registry=build_default_tool_registry(),
        active_persona="default",
    )
    return orch, stub


@pytest.mark.asyncio
async def test_mirror_tool_results_adds_user_echo(tmp_path: Path):
    orch, stub = _orch(tmp_path, mirror=True)
    res = await orch.run_llm_with_tools("Która godzina?")
    assert "po narzędziu" in (res.content or "").lower()
    assert len(stub.calls) >= 2
    second = stub.calls[1]
    assert any(
        m.get("role") == "user" and "Wynik narzędzia" in str(m.get("content", "")) for m in second
    )


@pytest.mark.asyncio
async def test_mirror_tool_results_off_no_echo_line(tmp_path: Path):
    orch, stub = _orch(tmp_path, mirror=False)
    await orch.run_llm_with_tools("Która godzina?")
    assert len(stub.calls) >= 2
    second = stub.calls[1]
    assert not any("Wynik narzędzia" in str(m.get("content", "")) for m in second)
