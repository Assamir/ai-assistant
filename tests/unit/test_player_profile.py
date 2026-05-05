"""Profil gracza YAML + snapshot repository."""

from __future__ import annotations

import pytest

from backend.db.migration_runner import MigrationRunner
from backend.db.repositories import PlayerContextSnapshotRepository, SessionRepository
from backend.services.player_profile import Character, GameEntry, PlayerProfile, PlayerProfileRepository


def test_player_profile_roundtrip_yaml(tmp_path):
    path = tmp_path / "player_profile.yaml"
    db_path = str(tmp_path / "t.db")
    MigrationRunner(db_path).run_migrations()
    repo = PlayerProfileRepository(str(path), db_path)
    p = PlayerProfile(
        games={
            "poe2": GameEntry(
                active_character="Hero",
                league="S2",
                characters=[
                    Character(name="Hero", char_class="Witch", build="RF", level=50),
                ],
            )
        }
    )
    repo.save(p)
    p2 = repo.load()
    assert "poe2" in p2.games
    assert p2.games["poe2"].active_character == "Hero"


def test_summary_for_game(tmp_path):
    path = tmp_path / "p.yaml"
    db_path = str(tmp_path / "d.db")
    MigrationRunner(db_path).run_migrations()
    repo = PlayerProfileRepository(str(path), db_path)
    p = PlayerProfile(
        games={
            "g1": GameEntry(
                active_character="X",
                league="L",
                characters=[Character(name="X", char_class="C", build="b")],
            )
        }
    )
    repo.save(p)
    s = repo.summary_for_game("g1")
    assert s and "X" in s and "L" in s


@pytest.mark.asyncio
async def test_snapshot_insert(migrated_db_path):
    chat_id = await SessionRepository(migrated_db_path).start_session()
    repo = PlayerContextSnapshotRepository(migrated_db_path)
    sid = await repo.insert(
        chat_id,
        "poe2",
        "Hero",
        trigger="session_start",
        character_class="Witch",
        build_name="RF",
        league="S2",
    )
    assert sid >= 1


@pytest.mark.asyncio
async def test_archive_game_entry_inserts_row(tmp_path):
    path = tmp_path / "player_profile.yaml"
    db_path = str(tmp_path / "arc.db")
    MigrationRunner(db_path).run_migrations()
    repo = PlayerProfileRepository(str(path), db_path)
    p = PlayerProfile(
        games={
            "poe2": GameEntry(
                active_character="Hero",
                league="S2",
                characters=[
                    Character(name="Hero", char_class="Witch", build="RF", level=50),
                ],
            )
        }
    )
    repo.save(p)
    aid = await repo.archive_game_entry(game_id="poe2", season="S2", reason="season_reset")
    assert aid == 1
    rows = await repo.list_archives(game="poe2")
    assert len(rows) == 1
    assert rows[0]["season"] == "S2"
    assert rows[0]["reason"] == "season_reset"
    assert "Hero" in rows[0]["yaml_snapshot"]


@pytest.mark.asyncio
async def test_archive_unknown_game_returns_none(tmp_path):
    path = tmp_path / "empty.yaml"
    db_path = str(tmp_path / "e.db")
    MigrationRunner(db_path).run_migrations()
    repo = PlayerProfileRepository(str(path), db_path)
    repo.save(PlayerProfile())
    aid = await repo.archive_game_entry(game_id="nope", season="S1", reason="manual")
    assert aid is None


def test_patch_game_league_and_archive_hint(tmp_path):
    path = tmp_path / "p.yaml"
    db_path = str(tmp_path / "x.db")
    MigrationRunner(db_path).run_migrations()
    repo = PlayerProfileRepository(str(path), db_path)
    repo.save(
        PlayerProfile(
            games={
                "poe2": GameEntry(
                    league="S1",
                    active_character="A",
                    characters=[Character(name="A", char_class="W")],
                )
            }
        )
    )
    out = repo.patch_game_entry(
        "poe2",
        league="S2",
        update_league=True,
        update_game_version=False,
    )
    assert out is not None
    assert out["league_changed"] is True
    assert out["archive_recommended"] is True
    assert out["previous_league"] == "S1"
    loaded = repo.load()
    assert loaded.games["poe2"].league == "S2"


def test_set_active_character(tmp_path):
    path = tmp_path / "a.yaml"
    db_path = str(tmp_path / "y.db")
    MigrationRunner(db_path).run_migrations()
    repo = PlayerProfileRepository(str(path), db_path)
    repo.save(
        PlayerProfile(
            games={
                "g1": GameEntry(
                    characters=[
                        Character(name="One", char_class="X"),
                        Character(name="Two", char_class="Y"),
                    ],
                )
            }
        )
    )
    bad = repo.set_active_character_name("g1", "Nope")
    assert bad.get("ok") is False
    good = repo.set_active_character_name("g1", "Two")
    assert good.get("ok") is True
    assert repo.load().games["g1"].active_character == "Two"
