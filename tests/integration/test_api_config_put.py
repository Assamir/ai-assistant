"""PUT /api/v1/config — merge, zapis YAML, reload kontekstu."""

from __future__ import annotations

import pytest
import yaml
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.mark.asyncio
async def test_put_config_persists_and_updates_context(monkeypatch, tmp_path):
    root = tmp_path / "content"
    root.mkdir()
    (root / "config").mkdir()
    cfg_path = root / "config" / "config.yaml"
    cfg_path.write_text(
        yaml.safe_dump({"llm": {"temperature": 0.77, "max_tokens": 400}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ASSY_GENERAL__CONTENT_ROOT", str(root))

    from backend.api.app_context import create_app_context

    ctx = create_app_context()
    assert ctx.resolved_config_path is not None
    app.state.ctx = ctx

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.put("/api/v1/config", json={"patch": {"llm": {"temperature": 0.21}}})
            assert res.status_code == 200
            body = res.json()
            assert body.get("ok") is True
            assert body["data"]["llm"]["temperature"] == pytest.approx(0.21)

            on_disk = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
            assert on_disk["llm"]["temperature"] == pytest.approx(0.21)

            assert app.state.ctx.config.llm.temperature == pytest.approx(0.21)
    finally:
        await ctx.llm_client.aclose()
        app.state.ctx = None


@pytest.mark.asyncio
async def test_put_config_422_on_invalid_patch(monkeypatch, tmp_path):
    root = tmp_path / "content2"
    root.mkdir()
    (root / "config").mkdir()
    cfg_path = root / "config" / "config.yaml"
    cfg_path.write_text(yaml.safe_dump({"log_level": "INFO"}), encoding="utf-8")
    monkeypatch.setenv("ASSY_GENERAL__CONTENT_ROOT", str(root))

    from backend.api.app_context import create_app_context

    ctx = create_app_context()
    app.state.ctx = ctx
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.put(
                "/api/v1/config",
                json={"patch": {"llm": {"temperature": "not-a-float"}}},
            )
            assert res.status_code == 422
    finally:
        await ctx.llm_client.aclose()
        app.state.ctx = None
