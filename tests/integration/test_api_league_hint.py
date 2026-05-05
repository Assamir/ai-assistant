"""POST check-league-hint."""

from __future__ import annotations

import pytest
import yaml
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.mark.asyncio
async def test_check_league_hint_mismatch(monkeypatch, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "config").mkdir()
    (root / "config" / "config.yaml").write_text(yaml.safe_dump({"log_level": "INFO"}), encoding="utf-8")
    monkeypatch.setenv("ASSY_GENERAL__CONTENT_ROOT", str(root))
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "data" / "player_profile.yaml").write_text(
        yaml.safe_dump(
            {
                "games": {
                    "poe2": {
                        "league": "OldLeagueX",
                        "active_character": "H",
                        "characters": [{"name": "H", "class": "W"}],
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
            return {
                "ok": True,
                "heading": "PoE2",
                "abstract": "Totally different season name here",
                "related_texts": [],
            }
        return {"ok": False}

    monkeypatch.setattr(ctx.tool_registry, "invoke", fake_invoke)

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                "/api/v1/player-profile/games/poe2/check-league-hint",
                json={"broadcast": False},
            )
            assert res.status_code == 200
            data = res.json()
            assert data.get("mismatch_hint") is True
            assert data.get("archive_suggested") is True
    finally:
        await ctx.llm_client.aclose()
        app.state.ctx = None
