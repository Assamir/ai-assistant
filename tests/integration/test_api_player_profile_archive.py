"""POST/GET player-profile archives — SQLite ``player_profile_archives``."""

from __future__ import annotations

import pytest
import yaml
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.mark.asyncio
async def test_post_player_profile_archive_persists(monkeypatch, tmp_path):
    root = tmp_path / "content"
    root.mkdir()
    (root / "config").mkdir()
    cfg_path = root / "config" / "config.yaml"
    cfg_path.write_text(
        yaml.safe_dump({"log_level": "INFO", "general": {"content_root": str(root)}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ASSY_GENERAL__CONTENT_ROOT", str(root))
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "player_profile.yaml").write_text(
        yaml.safe_dump(
            {
                "games": {
                    "poe2": {
                        "active_character": "Hero",
                        "league": "S2",
                        "characters": [
                            {
                                "name": "Hero",
                                "class": "Witch",
                                "build": "RF",
                                "level": 50,
                            }
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
            res = await ac.post(
                "/api/v1/player-profile/games/poe2/archive",
                json={"season": "Season 2", "reason": "season_reset"},
            )
            assert res.status_code == 200
            assert res.json()["archive_id"] >= 1

            listed = await ac.get("/api/v1/player-profile/archives", params={"game": "poe2"})
            assert listed.status_code == 200
            archives = listed.json()["archives"]
            assert len(archives) == 1
            assert archives[0]["season"] == "Season 2"
            assert "Hero" in archives[0]["yaml_snapshot"]
    finally:
        await ctx.llm_client.aclose()
        app.state.ctx = None


@pytest.mark.asyncio
async def test_post_player_profile_archive_404_unknown_game(monkeypatch, tmp_path):
    root = tmp_path / "content2"
    root.mkdir()
    (root / "config").mkdir()
    cfg_path = root / "config" / "config.yaml"
    cfg_path.write_text(
        yaml.safe_dump({"log_level": "INFO", "general": {"content_root": str(root)}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ASSY_GENERAL__CONTENT_ROOT", str(root))
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "data" / "player_profile.yaml").write_text(
        yaml.safe_dump({"games": {}}),
        encoding="utf-8",
    )

    from backend.api.app_context import create_app_context

    ctx = create_app_context()
    app.state.ctx = ctx
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                "/api/v1/player-profile/games/poe2/archive",
                json={"season": "S1", "reason": "backup"},
            )
            assert res.status_code == 404
            assert res.json()["detail"]["code"] == "GAME_NOT_IN_PROFILE"
    finally:
        await ctx.llm_client.aclose()
        app.state.ctx = None
