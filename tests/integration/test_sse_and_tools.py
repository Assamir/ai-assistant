"""SSE streaming (/voice/chat?stream) i endpoint /tools."""

from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


# ─── Fixture ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def http_client(tmp_path):
    from pathlib import Path as Pth

    from backend.api.app_context import create_app_context
    from backend.core.orchestrator import ConversationOrchestrator
    from backend.db.migration_runner import MigrationRunner
    from backend.mcp.context_tools import register_context_dependent_mcp_tools
    from backend.mcp.registry import build_default_tool_registry
    from backend.services.player_profile import PlayerProfileRepository

    db_path = str(tmp_path / "sse_ctx.db")
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
    register_context_dependent_mcp_tools(ctx)
    ctx.tts_engine = None
    app.state.ctx = ctx
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, ctx
    try:
        await ctx.llm_client.aclose()
    finally:
        app.state.ctx = None


# ─── /api/v1/tools ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tools_endpoint_200(http_client):
    """/tools → 200 + lista narzędzi."""
    ac, _ = http_client
    r = await ac.get("/api/v1/tools")
    assert r.status_code == 200
    body = r.json()
    assert "tools" in body
    assert isinstance(body["tools"], list)
    assert len(body["tools"]) > 0


@pytest.mark.asyncio
async def test_tools_contains_expected_names(http_client):
    """Rejestr domyślny zawiera wszystkie 5 narzędzi."""
    ac, _ = http_client
    r = await ac.get("/api/v1/tools")
    names = {t["name"] for t in r.json()["tools"]}
    assert "get_current_time" in names
    assert "calculator" in names
    assert "random_choice" in names
    assert "dice_roll" in names
    assert "format_duration" in names


@pytest.mark.asyncio
async def test_tools_each_has_name_and_description(http_client):
    """Każde narzędzie ma niepuste 'name' i 'description'."""
    ac, _ = http_client
    r = await ac.get("/api/v1/tools")
    for tool in r.json()["tools"]:
        assert tool["name"]
        assert isinstance(tool["description"], str)


# ─── /api/v1/voice/chat SSE ──────────────────────────────────────────────────


async def _fake_stream(*args, **kwargs) -> AsyncIterator[str]:
    yield "Cześć"
    yield ", jak"
    yield " mogę pomóc?"


@pytest.mark.asyncio
async def test_voice_chat_sse_status_and_content_type(http_client):
    """POST /voice/chat stream=True → 200 text/event-stream."""
    ac, ctx = http_client
    with patch.object(ctx.orchestrator, "stream_reply_tokens", new=_fake_stream):
        r = await ac.post("/api/v1/voice/chat", json={"text": "Hej!", "stream": True})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]


@pytest.mark.asyncio
async def test_voice_chat_sse_contains_token_events(http_client):
    """SSE body zawiera zdarzenia 'token' z treścią odpowiedzi."""
    ac, ctx = http_client
    with patch.object(ctx.orchestrator, "stream_reply_tokens", new=_fake_stream):
        r = await ac.post("/api/v1/voice/chat", json={"text": "Hej!", "stream": True})
    body = r.text
    assert "event: token" in body
    assert "Cześć" in body


@pytest.mark.asyncio
async def test_voice_chat_sse_ends_with_done(http_client):
    """SSE body kończy się zdarzeniem 'done' z session_id / chat_session_id."""
    import json as _json

    ac, ctx = http_client
    with patch.object(ctx.orchestrator, "stream_reply_tokens", new=_fake_stream):
        r = await ac.post("/api/v1/voice/chat", json={"text": "Hej!", "stream": True})
    assert "event: done" in r.text
    for line in r.text.split("\n"):
        if line.startswith("data: ") and '"ok"' in line:
            payload = _json.loads(line[6:])
            assert payload.get("ok") is True
            assert payload.get("session_id")
            assert payload.get("chat_session_id") is not None
            assert payload.get("tool_calls") == []
            break
    else:
        raise AssertionError("brak linii data: z done")


@pytest.mark.asyncio
async def test_voice_chat_sse_persists_sqlite_messages(http_client):
    """SSE zapisuje user + assistant do tabeli messages (jak JSON / WS)."""
    ac, ctx = http_client
    from backend.db.repositories import MessageRepository

    sid = "sse-sqlite-session"
    with patch.object(ctx.orchestrator, "stream_reply_tokens", new=_fake_stream):
        await ac.post(
            "/api/v1/voice/chat",
            json={"text": "Hej SSE!", "stream": True, "session_id": sid},
        )
    db_id = ctx.db_session_by_ws.get(sid)
    assert db_id is not None
    msgs = await MessageRepository(ctx.db_path).get_messages_for_session(db_id)
    roles = {m["source"] for m in msgs}
    assert "user" in roles and "assistant" in roles


@pytest.mark.asyncio
async def test_voice_chat_sse_contains_emotion_event(http_client):
    """SSE body zawiera zdarzenie 'emotion'."""
    ac, ctx = http_client
    with patch.object(ctx.orchestrator, "stream_reply_tokens", new=_fake_stream):
        r = await ac.post("/api/v1/voice/chat", json={"text": "Hej!", "stream": True})
    assert "event: emotion" in r.text


@pytest.mark.asyncio
async def test_voice_chat_sse_via_accept_header(http_client):
    """Accept: text/event-stream bez stream=True → też SSE."""
    ac, ctx = http_client
    with patch.object(ctx.orchestrator, "stream_reply_tokens", new=_fake_stream):
        r = await ac.post(
            "/api/v1/voice/chat",
            json={"text": "Hej!"},
            headers={"Accept": "text/event-stream"},
        )
    assert r.status_code == 200
    assert "event: token" in r.text


@pytest.mark.asyncio
async def test_voice_chat_sse_appends_conversation(http_client):
    """Po SSE stream wiadomości user+assistant są w ConversationStore."""
    ac, ctx = http_client
    import uuid as _uuid
    sess = str(_uuid.uuid4())
    with patch.object(ctx.orchestrator, "stream_reply_tokens", new=_fake_stream):
        await ac.post(
            "/api/v1/voice/chat",
            json={"text": "Hej!", "stream": True, "session_id": sess},
        )
    hist = ctx.conversation.tail(sess)
    assert any(m["role"] == "user" for m in hist)
    assert any(m["role"] == "assistant" for m in hist)
