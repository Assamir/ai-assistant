"""Endpointy /api/v1/llm/* — mock LLMModelManager."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.ai.llm_models_catalog import ModelEntry
from backend.config.schema import ConfigSchema
from backend.main import app
from backend.services.llm_model_manager import DownloadedModel


def _make_ctx(mgr=None, llm_provider="local"):
    cfg = ConfigSchema()
    cfg.llm.provider = llm_provider  # type: ignore[assignment]
    ctx = MagicMock()
    ctx.config = cfg
    ctx.llm_model_manager = mgr
    ctx.content_root = Path(".")
    ctx.websocket_manager = MagicMock()
    return ctx


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.state.ctx = None


@pytest.mark.asyncio
async def test_get_providers(client: AsyncClient):
    app.state.ctx = _make_ctx(llm_provider="lm_studio")
    res = await client.get("/api/v1/llm/providers")
    assert res.status_code == 200
    body = res.json()
    assert body["active"] == "lm_studio"
    ids = [p["id"] for p in body["providers"]]
    assert "lm_studio" in ids and "local" in ids and "openrouter" in ids


@pytest.mark.asyncio
async def test_list_models_with_manager(client: AsyncClient):
    mgr = MagicMock()
    mgr.list_catalog.return_value = [
        ModelEntry(
            model_id="unsloth/gemma-3n-E4B-it-GGUF",
            display_name="Gemma 3n",
            default_quant="Q4_K_M",
        ),
    ]
    mgr.list_downloaded.return_value = [
        DownloadedModel(
            model_id="unsloth/gemma-3n-E4B-it-GGUF",
            local_path="/tmp/x.gguf",
            size_bytes=1234,
            quant="Q4_K_M",
        ),
    ]
    app.state.ctx = _make_ctx(mgr=mgr)
    res = await client.get("/api/v1/llm/models")
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["model_id"] == "unsloth/gemma-3n-E4B-it-GGUF"
    assert item["downloaded"] is True
    assert item["size_bytes"] == 1234


@pytest.mark.asyncio
async def test_add_custom_model(client: AsyncClient):
    mgr = MagicMock()
    app.state.ctx = _make_ctx(mgr=mgr)
    res = await client.post("/api/v1/llm/models", json={
        "model_id": "TheBloke/Mistral-7B-Instruct-v0.2-GGUF",
        "display_name": "Mistral 7B",
        "default_quant": "Q5_K_M",
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["entry"]["is_custom"] is True
    mgr.add_custom_model.assert_called_once()


@pytest.mark.asyncio
async def test_add_custom_model_invalid_id(client: AsyncClient):
    app.state.ctx = _make_ctx(mgr=MagicMock())
    res = await client.post("/api/v1/llm/models", json={
        "model_id": "bad-format",  # brak slasha
        "display_name": "X",
    })
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "INVALID_MODEL_ID"


@pytest.mark.asyncio
async def test_download_model_calls_ensure_downloaded(client: AsyncClient):
    mgr = MagicMock()

    async def fake_ensure(*args, **kwargs):
        return DownloadedModel(
            model_id="owner/repo",
            local_path="/tmp/m.gguf",
            size_bytes=999,
            quant="Q4_K_M",
        )

    mgr.ensure_downloaded = fake_ensure
    app.state.ctx = _make_ctx(mgr=mgr)
    res = await client.post("/api/v1/llm/models/owner%2Frepo/download")
    assert res.status_code == 200
    body = res.json()
    assert body["model_id"] == "owner/repo"
    assert body["size_bytes"] == 999


@pytest.mark.asyncio
async def test_delete_model_removes_cache(client: AsyncClient):
    mgr = MagicMock()
    mgr.remove_downloaded.return_value = True
    mgr.remove_custom_model.return_value = False
    app.state.ctx = _make_ctx(mgr=mgr)
    res = await client.delete("/api/v1/llm/models/owner%2Frepo?scope=cache")
    assert res.status_code == 200
    body = res.json()
    assert body["removed_cache"] is True
    assert body["removed_catalog"] is False
    mgr.remove_downloaded.assert_called_once_with("owner/repo")
    mgr.remove_custom_model.assert_not_called()
