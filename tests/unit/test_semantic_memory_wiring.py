"""Integracja init_semantic_memory + wstrzyknięcie KB w orkiestratorze."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.app_context import init_semantic_memory
from backend.ai.llm_client import ChatCompletionResult
from backend.config.schema import AIControlConfig, ConfigSchema, LLMConfig, MemoryConfig
from backend.core.command_matching import CommandMatcher
from backend.core.orchestrator import ConversationOrchestrator
from backend.core.persona_loader import PersonaLoader
from backend.core.prompt_builder import PromptBuilder
from backend.mcp.registry import build_default_tool_registry


def test_init_semantic_memory_disabled(tmp_path: Path):
    root = tmp_path / "cr"
    root.mkdir()
    cfg = ConfigSchema(memory=MemoryConfig(enabled=False))
    sr, ing, w = init_semantic_memory(cfg, root)
    assert sr is None and ing is None and w is None


def test_init_semantic_memory_ingests_knowledge_dir(tmp_path: Path):
    root = tmp_path / "cr"
    root.mkdir()
    kdir = root / "knowledge"
    kdir.mkdir()
    (kdir / "note.md").write_text("unique_ingest_wire_phrase_alpha\n", encoding="utf-8")
    cfg = ConfigSchema(
        memory=MemoryConfig(
            enabled=True,
            chroma_persist=False,
            ingest_on_startup=True,
            watch_knowledge=False,
        ),
    )
    sr, ing, w = init_semantic_memory(cfg, root)
    assert sr is not None and ing is not None
    assert w is None
    hits = sr.recall_knowledge("unique_ingest_wire", k=2)
    assert any("unique_ingest_wire" in h for h in hits)


@pytest.mark.asyncio
async def test_orchestrator_inserts_kb_into_messages(tmp_path: Path):
    captured: list[list] = []

    async def _cc(messages, *, tools=None, max_tokens=None):
        captured.append(list(messages))
        return ChatCompletionResult(content="[EMO:neutral] git.")

    recall = MagicMock()
    recall.recall_knowledge = MagicMock(return_value=["boss ma fazę ognia unikalna_fraza_xyz"])

    personas_dir = tmp_path / "personas"
    personas_dir.mkdir()
    cfg = ConfigSchema(
        llm=LLMConfig(api_base_url="http://stub/", model_name="stub"),
        ai_runtime=AIControlConfig(max_context_tokens=2048, max_tool_calls_per_turn=3),
        memory=MemoryConfig(enabled=True, inject_into_prompt=True, recall_top_k=4),
    )
    lm = MagicMock()
    lm.chat_completion = AsyncMock(side_effect=_cc)
    orch = ConversationOrchestrator(
        configuration=cfg,
        lm_client=lm,  # type: ignore[arg-type]
        prompt_builder=PromptBuilder(max_context_tokens=2048),
        persona_loader=PersonaLoader(personas_dir),
        command_matcher=CommandMatcher(fuzzy=True),
        tool_registry=build_default_tool_registry(),
        active_persona="default",
        semantic_recall=recall,
    )
    await orch.handle_user_message("opisz walkę")
    assert captured
    blob = "\n".join(str(m.get("content", "")) for m in captured[0])
    assert "unikalna_fraza_xyz" in blob
    recall.recall_knowledge.assert_called_once()
