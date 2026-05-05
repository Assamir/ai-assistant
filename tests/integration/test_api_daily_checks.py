"""REST: daily meta checks."""

from __future__ import annotations

import pytest
import yaml
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.mark.asyncio
async def test_daily_checks_run_and_list(monkeypatch, tmp_path):
    root = tmp_path / "content"
    root.mkdir()
    (root / "config").mkdir()
    cfg_path = root / "config" / "config.yaml"
    cfg_path.write_text(yaml.safe_dump({"log_level": "INFO"}), encoding="utf-8")
    monkeypatch.setenv("ASSY_GENERAL__CONTENT_ROOT", str(root))
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "player_profile.yaml").write_text(
        yaml.safe_dump(
            {
                "games": {
                    "poe2": {
                        "league": "S2",
                        "active_character": "Hero",
                        "characters": [{"name": "Hero", "class": "Witch", "build": "RF", "level": 50}],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    from backend.api.app_context import create_app_context

    ctx = create_app_context()
    app.state.ctx = ctx

    async def fake_invoke(name: str, arguments=None, **kwargs):
        if name == "web_search":
            return {"ok": True, "abstract": "Balance patch", "related_texts": ["note"]}
        return {"ok": False, "error": "unknown tool"}

    monkeypatch.setattr(ctx.tool_registry, "invoke", fake_invoke)

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post("/api/v1/daily-checks/run", json={"game": "poe2", "force": True})
            assert res.status_code == 200
            body = res.json()
            assert body.get("skipped") is False
            assert body.get("check_id") >= 1
            assert "Balance patch" in body.get("summary", "")
            kfp = body.get("knowledge_file_path")
            assert kfp and "knowledge/daily_checks" in kfp.replace("\\", "/")
            assert (root / kfp).is_file()

            listed = await ac.get("/api/v1/daily-checks", params={"game": "poe2"})
            assert listed.status_code == 200
            checks = listed.json()["checks"]
            assert len(checks) >= 1
            assert checks[0]["has_changes"] is True
            assert checks[0].get("knowledge_file_path")

            res2 = await ac.post("/api/v1/daily-checks/run", json={"game": "poe2", "force": False})
            assert res2.status_code == 200
            assert res2.json().get("skipped") is True
    finally:
        await ctx.llm_client.aclose()
        app.state.ctx = None


@pytest.mark.asyncio
async def test_daily_checks_run_404(monkeypatch, tmp_path):
    root = tmp_path / "content2"
    root.mkdir()
    (root / "config").mkdir()
    (root / "config" / "config.yaml").write_text(yaml.safe_dump({"log_level": "INFO"}), encoding="utf-8")
    monkeypatch.setenv("ASSY_GENERAL__CONTENT_ROOT", str(root))
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "data" / "player_profile.yaml").write_text(yaml.safe_dump({"games": {}}), encoding="utf-8")

    from backend.api.app_context import create_app_context

    ctx = create_app_context()
    app.state.ctx = ctx
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post("/api/v1/daily-checks/run", json={"game": "poe2", "force": True})
            assert res.status_code == 404
    finally:
        await ctx.llm_client.aclose()
        app.state.ctx = None
