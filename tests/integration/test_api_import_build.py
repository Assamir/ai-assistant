"""Integration tests for POST /api/v1/player-profile/games/{game}/import-build."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


def _make_ctx(*, profile_ok: bool = True):
    ctx = MagicMock()
    ctx.config.general.content_root = "."
    ctx.config.general.assistant_name = "Aria"

    store = MagicMock() if profile_ok else None
    ctx.player_profile_store = store

    registry = MagicMock()
    ctx.tool_registry = registry

    ws_mgr = MagicMock()
    ws_mgr.iter_session_ids.return_value = []
    ctx.websocket_manager = ws_mgr
    return ctx


@pytest.fixture
def app_ok():
    ctx = _make_ctx(profile_ok=True)
    from backend.api.routes import ctx_dep
    app.dependency_overrides[ctx_dep] = lambda: ctx
    yield app, ctx
    app.dependency_overrides.clear()


@pytest.fixture
def app_no_profile():
    ctx = _make_ctx(profile_ok=False)
    from backend.api.routes import ctx_dep
    app.dependency_overrides[ctx_dep] = lambda: ctx
    yield app, ctx
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_import_build_503_no_profile(app_no_profile):
    app, _ = app_no_profile
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/player-profile/games/poe2/import-build",
            json={"url": "https://maxroll.gg/poe2/build"},
        )
    assert res.status_code == 503


@pytest.mark.asyncio
async def test_import_build_success(app_ok):
    app, ctx = app_ok
    import_result = {"ok": True, "game": "poe2", "character": "SparkyBoy", "build": "LA Build", "url": "https://example.com"}
    with patch("backend.services.build_import.import_build_from_url", new=AsyncMock(return_value=import_result)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                "/api/v1/player-profile/games/poe2/import-build",
                json={"url": "https://maxroll.gg/poe2/build"},
            )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["character"] == "SparkyBoy"


@pytest.mark.asyncio
async def test_import_build_422_on_scrape_failure(app_ok):
    app, ctx = app_ok
    fail_result = {"ok": False, "error": "scrape_failed"}
    with patch("backend.services.build_import.import_build_from_url", new=AsyncMock(return_value=fail_result)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                "/api/v1/player-profile/games/poe2/import-build",
                json={"url": "https://maxroll.gg/poe2/build"},
            )
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert detail["error"] == "scrape_failed"


@pytest.mark.asyncio
async def test_import_build_422_on_missing_url(app_ok):
    app, _ = app_ok
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/player-profile/games/poe2/import-build",
            json={},
        )
    assert res.status_code == 422
