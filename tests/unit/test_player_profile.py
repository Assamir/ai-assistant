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
