"""GameObserver wired into AppContext, lifespan, orchestrator prompt, /status."""

from __future__ import annotations

import asyncio
from typing import List, Tuple
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.app_context import AppContext, make_game_emitter
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


# ─── make_game_emitter ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_emitter_updates_orchestrator_state(http_client):
    """make_game_emitter sets orchestrator.state['current_game'] on game_detected."""
    _, ctx = http_client
    emitter = make_game_emitter(ctx)
    await emitter(
        "game_detected",
        {"game": "Stellaris", "game_id": "stellaris", "active": True},
    )
    assert ctx.orchestrator.state.get("current_game") == "Stellaris"
    assert ctx.orchestrator.state.get("current_game_profile_id") == "stellaris"


@pytest.mark.asyncio
async def test_emitter_clears_on_game_close(http_client):
    """Emitter sets current_game=None when game closes."""
    _, ctx = http_client
    emitter = make_game_emitter(ctx)
    await emitter(
        "game_detected",
        {"game": "Stellaris", "game_id": "stellaris", "active": True},
    )
    await emitter("game_detected", {"game": None, "active": False})
    assert ctx.orchestrator.state.get("current_game") is None
    assert ctx.orchestrator.state.get("current_game_profile_id") is None


@pytest.mark.asyncio
async def test_emitter_ignores_non_game_events(http_client):
    """Emitter does not crash on unrecognised event names."""
    _, ctx = http_client
    emitter = make_game_emitter(ctx)
    await emitter("some_other_event", {"foo": "bar"})
    assert "current_game" not in ctx.orchestrator.state or True  # no crash


# ─── AppContext has game_observer ────────────────────────────────────────────


def test_create_app_context_has_game_observer(http_client):
    """create_app_context() returns AppContext with a non-None game_observer."""
    _, ctx = http_client
    from backend.services.game_observer import GameObserver
    assert ctx.game_observer is not None
    assert isinstance(ctx.game_observer, GameObserver)


# ─── /status endpoint includes observer ──────────────────────────────────────


@pytest.mark.asyncio
async def test_status_includes_observer(http_client):
    """/status returns an 'observer' key with running and current_game."""
    ac, _ = http_client
    r = await ac.get("/api/v1/status")
    assert r.status_code == 200
    body = r.json()
    assert "observer" in body
    obs = body["observer"]
    assert "running" in obs
    assert "vision_loop_running" in obs
    assert "current_game" in obs


@pytest.mark.asyncio
async def test_status_observer_not_running_without_lifespan(http_client):
    """Without lifespan start, observer.is_running is False."""
    ac, _ = http_client
    r = await ac.get("/api/v1/status")
    body = r.json()
    assert body["observer"]["running"] is False


@pytest.mark.asyncio
async def test_status_observer_current_game_reflects_state(http_client):
    """After emitter fires, /status shows updated current_game."""
    ac, ctx = http_client
    emitter = make_game_emitter(ctx)
    await emitter("game_detected", {"game": "Path of Exile 2", "active": True})
    r = await ac.get("/api/v1/status")
    body = r.json()
    assert body["observer"]["current_game"] == "Path of Exile 2"


# ─── Orchestrator prompt includes observer_context ────────────────────────────


@pytest.mark.asyncio
async def test_observer_context_injected_into_build_messages(http_client):
    """When current_game is set, build_messages receives observer_context."""
    _, ctx = http_client
    ctx.orchestrator.state["current_game"] = "Stellaris"

    captured_kwargs: list = []
    original = ctx.orchestrator._pb.build_messages

    def capturing(*args, **kwargs):
        captured_kwargs.append(kwargs)
        return original(*args, **kwargs)

    ctx.orchestrator._pb.build_messages = capturing

    fake_result = AsyncMock()
    fake_result.content = "[EMO:thinking] Dobra gra."
    fake_result.tool_calls = []

    with patch.object(ctx.orchestrator._llm, "chat_completion", return_value=fake_result):
        await ctx.orchestrator.run_llm_with_tools("co grasz?")

    assert len(captured_kwargs) >= 1
    obs_ctx = captured_kwargs[0].get("observer_context")
    assert obs_ctx is not None
    assert "Stellaris" in obs_ctx


@pytest.mark.asyncio
async def test_observer_context_none_when_no_game(http_client):
    """When no game is active, observer_context is None."""
    _, ctx = http_client
    ctx.orchestrator.state.pop("current_game", None)

    captured_kwargs: list = []
    original = ctx.orchestrator._pb.build_messages

    def capturing(*args, **kwargs):
        captured_kwargs.append(kwargs)
        return original(*args, **kwargs)

    ctx.orchestrator._pb.build_messages = capturing

    fake_result = AsyncMock()
    fake_result.content = "[EMO:neutral] Nic nie gram."
    fake_result.tool_calls = []

    with patch.object(ctx.orchestrator._llm, "chat_completion", return_value=fake_result):
        await ctx.orchestrator.run_llm_with_tools("co słychać?")

    assert len(captured_kwargs) >= 1
    obs_ctx = captured_kwargs[0].get("observer_context")
    assert obs_ctx is None
