"""DELETE /api/v1/knowledge — usuniecie chunków wiedzy semantycznej."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


def _make_ctx(semantic_recall=None):
    ctx = MagicMock()
    ctx.semantic_recall = semantic_recall
    ctx.db_path = ":memory:"
    return ctx


@pytest.fixture
async def client_no_memory():
    app.state.ctx = _make_ctx(semantic_recall=None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.state.ctx = None


@pytest.fixture
async def client_with_memory():
    sr = MagicMock()
    sr.remove_knowledge_chunks_where = MagicMock(return_value=3)
    app.state.ctx = _make_ctx(semantic_recall=sr)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.state.ctx = None


@pytest.mark.asyncio
async def test_delete_knowledge_no_memory_returns_503(client_no_memory: AsyncClient):
    res = await client_no_memory.delete("/api/v1/knowledge", params={"source_path": "stellaris.md"})
    assert res.status_code == 503
    body = res.json()
    assert body["detail"]["code"] == "MEMORY_UNAVAILABLE"


@pytest.mark.asyncio
async def test_delete_knowledge_returns_removed_count(client_with_memory: AsyncClient):
    res = await client_with_memory.delete("/api/v1/knowledge", params={"source_path": "stellaris.md"})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["removed"] == 3
    assert body["source_path"] == "stellaris.md"


@pytest.mark.asyncio
async def test_delete_knowledge_passes_source_path(client_with_memory: AsyncClient):
    sr = app.state.ctx.semantic_recall
    await client_with_memory.delete("/api/v1/knowledge", params={"source_path": "poe2_builds.md"})
    sr.remove_knowledge_chunks_where.assert_called_once_with({"source_path": "poe2_builds.md"})


@pytest.mark.asyncio
async def test_delete_knowledge_zero_removed(client_with_memory: AsyncClient):
    sr = app.state.ctx.semantic_recall
    sr.remove_knowledge_chunks_where = MagicMock(return_value=0)
    res = await client_with_memory.delete("/api/v1/knowledge", params={"source_path": "nonexistent.md"})
    assert res.status_code == 200
    body = res.json()
    assert body["removed"] == 0
    assert body["ok"] is True
