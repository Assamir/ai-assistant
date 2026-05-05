"""PATCH player-profile game meta + active character."""

from __future__ import annotations

import pytest
import yaml
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.mark.asyncio
async def test_patch_league_returns_archive_recommended(monkeypatch, tmp_path):
    root = tmp_path / "c"
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
                        "league": "Season1",
                        "active_character": "Hero",
                        "characters": [{"name": "Hero", "class": "Witch"}],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    from backend.api.app_context import create_app_context

    ctx = create_app_context()
    app.state.ctx = ctx
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.patch(
                "/api/v1/player-profile/games/poe2",
                json={"league": "Season2"},
            )
            assert res.status_code == 200
            body = res.json()
            assert body.get("archive_recommended") is True
            assert body.get("league_changed") is True
            assert body["profile"]["games"]["poe2"]["league"] == "Season2"
    finally:
        await ctx.llm_client.aclose()
        app.state.ctx = None


@pytest.mark.asyncio
async def test_post_active_character(monkeypatch, tmp_path):
    root = tmp_path / "c2"
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
                        "active_character": "A",
                        "characters": [
                            {"name": "A", "class": "W"},
                            {"name": "B", "class": "M"},
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    from backend.api.app_context import create_app_context

    ctx = create_app_context()
    app.state.ctx = ctx
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            bad = await ac.post(
                "/api/v1/player-profile/games/poe2/active-character",
                json={"character": "Z"},
            )
            assert bad.status_code == 422

            ok = await ac.post(
                "/api/v1/player-profile/games/poe2/active-character",
                json={"character": "B"},
            )
            assert ok.status_code == 200
            assert ok.json()["active_character"] == "B"
    finally:
        await ctx.llm_client.aclose()
        app.state.ctx = None
