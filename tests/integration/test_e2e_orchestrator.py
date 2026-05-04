"""E2E orkiestrator: mockowany LLM + narzędzia MCP (bez sieci/GPU)."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient

from backend.ai.llm_client import ChatCompletionResult
from backend.config.schema import AIControlConfig, ConfigSchema, LLMConfig
from backend.core.command_handlers import CommandExecutionResult
from backend.core.command_matching import CommandMatcher
from backend.core.orchestrator import ConversationOrchestrator
from backend.core.persona_loader import PersonaLoader
from backend.core.prompt_builder import PromptBuilder
from backend.mcp.registry import build_default_tool_registry
from backend.db.migration_runner import MigrationRunner
from backend.main import app
from backend.services.player_profile import PlayerProfileRepository


# ─── Stub LLM ────────────────────────────────────────────────────────────────


class _StubLLM:
    """Zwraca ChatCompletionResult kolejno — bez HTTP i GPU."""

    def __init__(self, *results: ChatCompletionResult) -> None:
        self._q = list(results)
        self._i = 0

    async def chat_completion(self, messages, *, tools=None, max_tokens=None) -> ChatCompletionResult:
        if self._i < len(self._q):
            r = self._q[self._i]
            self._i += 1
            return r
        return ChatCompletionResult(content="(stub pusty)")

    async def aclose(self) -> None:
        pass


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def build_orch(tmp_path: Path):
    """Fabryka ConversationOrchestrator ze stubem LLM i prawdziwym rejestrem MCP."""
    personas_dir = tmp_path / "personas"
    personas_dir.mkdir()

    def _make(stub: _StubLLM) -> ConversationOrchestrator:
        cfg = ConfigSchema(
            llm=LLMConfig(api_base_url="http://stub/", model_name="stub"),
            ai_runtime=AIControlConfig(max_context_tokens=2048, max_tool_calls_per_turn=3),
        )
        return ConversationOrchestrator(
            configuration=cfg,
            lm_client=stub,  # type: ignore[arg-type]
            prompt_builder=PromptBuilder(max_context_tokens=2048),
            persona_loader=PersonaLoader(personas_dir),
            command_matcher=CommandMatcher(fuzzy=True),
            tool_registry=build_default_tool_registry(),
            active_persona="default",
        )

    return _make


@pytest.fixture
async def http_stub_client(tmp_path: Path):
    """AsyncClient z app.state.ctx; SQLite w tmp_path (bez zapisu w data/ projektu)."""
    from backend.api.app_context import create_app_context
    from pathlib import Path as Pth

    db_path = str(tmp_path / "http_e2e.db")
    MigrationRunner(db_path).run_migrations()

    ctx = create_app_context()
    root = Pth(ctx.config.general.content_root).expanduser()
    ctx.db_path = db_path
    ctx.tool_registry = build_default_tool_registry(
        db_path=db_path,
        mcp_cfg=ctx.config.mcp,
        content_root=str(root.resolve()),
    )
    ctx.player_profile_store = PlayerProfileRepository(
        str((root / "data" / "player_profile.yaml").resolve()),
        db_path,
    )
    pers = ctx.orchestrator.state.get("active_persona", "default")
    if not isinstance(pers, str):
        pers = "default"
    ctx.orchestrator = ConversationOrchestrator(
        configuration=ctx.config,
        lm_client=ctx.llm_client,
        prompt_builder=ctx.prompt_builder,
        persona_loader=ctx.persona_loader,
        command_matcher=ctx.command_matcher,
        tool_registry=ctx.tool_registry,
        active_persona=pers,
        emitter=None,
        db_path=db_path,
        semantic_recall=ctx.semantic_recall,
        player_profile_repo=ctx.player_profile_store,
    )
    from backend.mcp.context_tools import register_context_dependent_mcp_tools

    register_context_dependent_mcp_tools(ctx)
    app.state.ctx = ctx
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, ctx
    try:
        await ctx.llm_client.aclose()
    finally:
        app.state.ctx = None


# ─── Testy orkiestratora ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_time_query_invokes_get_current_time(build_orch):
    """LLM wywołuje get_current_time → orkiestrator wykonuje narzędzie → wynik w odpowiedzi."""
    tc = {
        "id": "c1",
        "type": "function",
        "function": {"name": "get_current_time", "arguments": "{}"},
    }
    stub = _StubLLM(
        ChatCompletionResult(content="", tool_calls=[tc]),
        ChatCompletionResult(content="Aktualny czas to 12:00.", tool_calls=None),
    )
    result = await build_orch(stub).handle_user_message("Która jest godzina?")

    assert result.success is True
    assert "12:00" in (result.message or "")
    assert stub._i == 2


@pytest.mark.asyncio
async def test_calculator_tool_call_round_trip(build_orch):
    """LLM wywołuje calculator(2+2*3) → wynik 8 → odpowiedź końcowa zawiera 8."""
    tc = {
        "id": "c2",
        "type": "function",
        "function": {"name": "calculator", "arguments": '{"expression":"2+2*3"}'},
    }
    stub = _StubLLM(
        ChatCompletionResult(content="", tool_calls=[tc]),
        ChatCompletionResult(content="Wynik: 8", tool_calls=None),
    )
    result = await build_orch(stub).handle_user_message("Oblicz 2+2*3")

    assert result.success is True
    assert "8" in (result.message or "")
    assert stub._i == 2


@pytest.mark.asyncio
async def test_direct_reply_without_tools(build_orch):
    """LLM odpowiada bez tool_calls — jeden round trip."""
    stub = _StubLLM(ChatCompletionResult(content="Cześć, jak mogę pomóc?"))
    result = await build_orch(stub).handle_user_message("Cześć!")

    assert result.success is True
    assert result.message
    assert stub._i == 1


@pytest.mark.asyncio
async def test_builtin_command_bypasses_llm(build_orch):
    """Komenda wbudowana (idź spać) trafia do handlera wbudowanego — LLM nie wywoływany."""
    stub = _StubLLM()
    result = await build_orch(stub).handle_user_message("idź spać")

    assert result.success is True
    assert stub._i == 0


@pytest.mark.asyncio
async def test_tool_result_forwarded_to_second_llm_call(build_orch):
    """W drugiej rundzie messages do LLM zawierają wiadomość roli 'tool'."""
    captured: list[list] = []

    class _Tracking(_StubLLM):
        async def chat_completion(self, messages, *, tools=None, max_tokens=None) -> ChatCompletionResult:
            captured.append(list(messages))
            return await super().chat_completion(messages, tools=tools, max_tokens=max_tokens)

    tc = {
        "id": "t1",
        "type": "function",
        "function": {"name": "get_current_time", "arguments": "{}"},
    }
    stub = _Tracking(
        ChatCompletionResult(content="", tool_calls=[tc]),
        ChatCompletionResult(content="Godzina sprawdzona."),
    )
    await build_orch(stub).handle_user_message("Podaj czas.")

    assert len(captured) == 2
    roles_round2 = {m.get("role") for m in captured[1]}
    assert "tool" in roles_round2


@pytest.mark.asyncio
async def test_calculator_error_propagated_gracefully(build_orch):
    """calculator(1/0) zwraca ok=False — LLM dostaje wynik błędu i odpowiada."""
    tc = {
        "id": "e1",
        "type": "function",
        "function": {"name": "calculator", "arguments": '{"expression":"1/0"}'},
    }
    stub = _StubLLM(
        ChatCompletionResult(content="", tool_calls=[tc]),
        ChatCompletionResult(content="Dzielenie przez zero jest niemożliwe."),
    )
    result = await build_orch(stub).handle_user_message("Podziel 1 przez 0")

    assert result.success is True
    assert stub._i == 2


@pytest.mark.asyncio
async def test_tool_calls_persisted_with_db_session(migrated_db_path, tmp_path: Path):
    """Przy db_path + db_chat_session_id zapisywane są wiersze tool_calls (DOK-10)."""
    from backend.config.schema import MCPConfig
    from backend.db.repositories import MessageRepository, SessionRepository, ToolCallsRepository

    personas_dir = tmp_path / "personas"
    personas_dir.mkdir()
    cfg = ConfigSchema(
        llm=LLMConfig(api_base_url="http://stub/", model_name="stub"),
        ai_runtime=AIControlConfig(max_context_tokens=2048, max_tool_calls_per_turn=3),
    )
    reg = build_default_tool_registry(db_path=migrated_db_path, mcp_cfg=MCPConfig(enabled=False))
    stub = _StubLLM(
        ChatCompletionResult(content="", tool_calls=[{
            "id": "c1",
            "type": "function",
            "function": {"name": "calculator", "arguments": '{"expression":"2+2"}'},
        }]),
        ChatCompletionResult(content="Wynik to 4.", tool_calls=None),
    )
    orch = ConversationOrchestrator(
        configuration=cfg,
        lm_client=stub,  # type: ignore[arg-type]
        prompt_builder=PromptBuilder(max_context_tokens=2048),
        persona_loader=PersonaLoader(personas_dir),
        command_matcher=CommandMatcher(fuzzy=True),
        tool_registry=reg,
        active_persona="default",
        db_path=migrated_db_path,
    )
    db_chat = await SessionRepository(migrated_db_path).start_session()
    await MessageRepository(migrated_db_path).create_message(db_chat, "user", "policz")
    await orch.handle_user_message("policz", conversation_tail=[], db_chat_session_id=db_chat)

    msgs = await MessageRepository(migrated_db_path).get_messages_for_session(db_chat)
    assist_with_tools = [m for m in msgs if m["source"] == "assistant" and m["content"] == "[wywołania narzędzi]"]
    assert assist_with_tools
    mid = int(assist_with_tools[0]["id"])
    rows = await ToolCallsRepository(migrated_db_path).list_for_message(mid)
    assert len(rows) == 1
    assert rows[0]["tool_name"] == "calculator"
    assert rows[0]["success"] in (1, True)
    assert "4" in (rows[0]["output_json"] or "")


# ─── HTTP E2E ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_voice_chat_content_and_emotion(http_stub_client):
    """/api/v1/voice/chat POST — odpowiedź orkiestratora mapowana na JSON."""
    ac, ctx = http_stub_client
    fake = CommandExecutionResult(success=True, message="Teraz jest 12:00.", emotion="neutral")
    with patch.object(ctx.orchestrator, "handle_user_message", new=AsyncMock(return_value=fake)):
        r = await ac.post("/api/v1/voice/chat", json={"text": "Która godzina?"})

    assert r.status_code == 200
    body = r.json()
    assert body["content"] == "Teraz jest 12:00."
    assert body["emotion"] == "neutral"
    assert "message_id" in body
    assert body["tool_calls"] == []
    assert body.get("session_id")
    assert body.get("chat_session_id") is not None


@pytest.mark.asyncio
async def test_voice_chat_rest_returns_tool_calls_summary(http_stub_client):
    """POST /voice/chat bez stream — ten sam `sessions.id` co WS, skrót tool_calls w JSON."""
    ac, ctx = http_stub_client
    stub = _StubLLM(
        ChatCompletionResult(content="", tool_calls=[{
            "id": "c1",
            "type": "function",
            "function": {"name": "calculator", "arguments": '{"expression":"2+2"}'},
        }]),
        ChatCompletionResult(content="Wynik to 4.", tool_calls=None),
    )
    pers = ctx.orchestrator.state.get("active_persona", "default")
    if not isinstance(pers, str):
        pers = "default"
    ctx.orchestrator = ConversationOrchestrator(
        configuration=ctx.config,
        lm_client=stub,  # type: ignore[arg-type]
        prompt_builder=ctx.prompt_builder,
        persona_loader=ctx.persona_loader,
        command_matcher=ctx.command_matcher,
        tool_registry=ctx.tool_registry,
        active_persona=pers,
        emitter=None,
        db_path=ctx.db_path,
        semantic_recall=ctx.semantic_recall,
        player_profile_repo=ctx.player_profile_store,
    )
    r = await ac.post("/api/v1/voice/chat", json={"text": "policz", "session_id": "rest-sess-1"})
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == "rest-sess-1"
    assert isinstance(body["chat_session_id"], int) and body["chat_session_id"] >= 1
    assert len(body["tool_calls"]) == 1
    assert body["tool_calls"][0]["tool_name"] == "calculator"
    assert body["tool_calls"][0]["success"] is True
    assert "4" in body["content"]


@pytest.mark.asyncio
async def test_voice_chat_empty_text_rejected(http_stub_client):
    """/voice/chat z pustym tekstem — FastAPI zwraca 422 (walidacja Pydantic)."""
    ac, _ = http_stub_client
    r = await ac.post("/api/v1/voice/chat", json={"text": ""})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_voice_synthesize_503_when_no_tts(http_stub_client):
    """/voice/synthesize — brak TTS engine → 503."""
    ac, _ = http_stub_client
    r = await ac.post("/api/v1/voice/synthesize", json={"text": "test", "emotion": "neutral"})
    assert r.status_code == 503
