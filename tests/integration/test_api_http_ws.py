"""HTTP (httpx ASGI) + WebSocket (Starlette TestClient)."""

from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from backend.main import app


@pytest.fixture
async def httpx_async():
    from backend.api.app_context import create_app_context

    app.state.ctx = create_app_context()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    try:
        ctx_obj = app.state.ctx
        if ctx_obj is not None:
            await ctx_obj.llm_client.aclose()
    finally:
        app.state.ctx = None


@pytest.mark.asyncio
async def test_api_health_httpx(httpx_async: AsyncClient):
    res = await httpx_async.get("/api/v1/health")
    assert res.status_code == 200



    body = res.json()
    assert body.get("status") == "ok"



@pytest.mark.asyncio



async def test_api_status_contains_phase(httpx_async: AsyncClient):


    res = await httpx_async.get("/api/v1/status")
    assert res.status_code == 200
    assert "orchestrator" in res.json()



@pytest.mark.asyncio
async def test_api_config_data(httpx_async: AsyncClient):
    res = await httpx_async.get("/api/v1/config")
    assert res.status_code == 200
    assert "data" in res.json()



def test_websocket_ping_pong_starlette():
    with TestClient(app, raise_server_exceptions=True) as client:
        with client.websocket_connect("/ws") as ws:
            hello = json.loads(ws.receive_text())

            assert hello.get("event") == "system_state"
            ws.send_json({"event": "ping", "payload": {}})
            incoming = ws.receive_text()


            data = json.loads(incoming)
            assert data.get("event") == "pong"



@pytest.mark.asyncio

async def test_voice_transcribe_503_when_no_stt(httpx_async: AsyncClient):
    files = {"audio": ("x.wav", b"PCM", "application/octet-stream")}


    r = await httpx_async.post("/api/v1/voice/transcribe", files=files)
    assert r.status_code == 503
