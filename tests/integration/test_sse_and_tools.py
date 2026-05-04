"""SSE streaming (/voice/chat?stream) i endpoint /tools."""

from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


# ─── Fixture ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def http_client():
    from backend.api.app_context import create_app_context

    ctx = create_app_context()
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
    """SSE body kończy się zdarzeniem 'done'."""
    ac, ctx = http_client
    with patch.object(ctx.orchestrator, "stream_reply_tokens", new=_fake_stream):
        r = await ac.post("/api/v1/voice/chat", json={"text": "Hej!", "stream": True})
    assert "event: done" in r.text


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
