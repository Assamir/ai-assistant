"""GameObserver — detekcja gier, emisja zdarzeń, cykl start/stop."""

from __future__ import annotations

import asyncio
from typing import List, Optional, Tuple

import pytest

from backend.config.schema import ObserverConfig
from backend.services.game_observer import KNOWN_GAMES, GameObserver
from backend.services.game_profile import profiles_from_known_games


# ─── Pomocnicze ──────────────────────────────────────────────────────────────


def _obs(
    processes: List[str],
    *,
    emit=None,
    interval: int = 60,
    state: Optional[dict] = None,
) -> GameObserver:
    """Fabryka obserwatora z zamockowanym _list_processes."""
    cfg = ObserverConfig(check_interval_seconds=interval)
    obs = GameObserver(
        cfg,
        emitter=emit,
        orchestrator_state=state,
        profiles_by_id=profiles_from_known_games(),
    )
    obs._list_processes = lambda: processes
    return obs


# ─── Detekcja gier ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_detects_stellaris():
    obs = _obs(["stellaris.exe", "chrome.exe"])
    game = await obs.tick()
    assert game == "Stellaris"


@pytest.mark.asyncio
async def test_detects_poe2():
    obs = _obs(["PathOfExile2.exe"])
    game = await obs.tick()
    assert game == "Path of Exile 2"


@pytest.mark.asyncio
async def test_case_insensitive_detection():
    obs = _obs(["STELLARIS.EXE"])
    game = await obs.tick()
    assert game == "Stellaris"


@pytest.mark.asyncio
async def test_no_known_game_returns_none():
    obs = _obs(["chrome.exe", "discord.exe", "spotify.exe"])
    game = await obs.tick()
    assert game is None


@pytest.mark.asyncio
async def test_empty_process_list_returns_none():
    obs = _obs([])
    game = await obs.tick()
    assert game is None


# ─── Emisja zdarzeń ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_emits_game_detected_on_first_detection():
    events: List[Tuple[str, dict]] = []

    async def capture(name, payload):
        events.append((name, payload))

    obs = _obs(["stellaris.exe"], emit=capture)
    await obs.tick()

    assert len(events) == 1
    evt, payload = events[0]
    assert evt == "game_detected"
    assert payload["game"] == "Stellaris"
    assert payload["game_id"] == "stellaris"
    assert payload["active"] is True


@pytest.mark.asyncio
async def test_no_emit_when_game_unchanged():
    events: List[Tuple] = []

    async def capture(name, payload):
        events.append((name, payload))

    obs = _obs(["stellaris.exe"], emit=capture)
    await obs.tick()
    await obs.tick()  # ten sam stan → bez emisji
    assert len(events) == 1


@pytest.mark.asyncio
async def test_emits_when_game_changes():
    events: List[dict] = []

    async def capture(name, payload):
        events.append(payload)

    obs = _obs(["stellaris.exe"], emit=capture)
    await obs.tick()

    obs._list_processes = lambda: ["pathofexile2.exe"]
    await obs.tick()

    assert len(events) == 2
    assert events[1]["game"] == "Path of Exile 2"


@pytest.mark.asyncio
async def test_emits_game_none_when_game_closes():
    events: List[dict] = []

    async def capture(name, payload):
        events.append(payload)

    obs = _obs(["stellaris.exe"], emit=capture)
    await obs.tick()

    obs._list_processes = lambda: ["chrome.exe"]
    await obs.tick()

    assert len(events) == 2
    assert events[1]["game"] is None
    assert events[1]["active"] is False


@pytest.mark.asyncio
async def test_no_emitter_does_not_crash():
    obs = _obs(["stellaris.exe"], emit=None)
    game = await obs.tick()
    assert game == "Stellaris"


# ─── Stan wewnętrzny ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_current_game_updated_after_tick():
    obs = _obs(["stellaris.exe"])
    assert obs.current_game is None
    await obs.tick()
    assert obs.current_game == "Stellaris"


@pytest.mark.asyncio
async def test_current_game_resets_to_none():
    obs = _obs(["stellaris.exe"])
    await obs.tick()
    obs._list_processes = lambda: []
    await obs.tick()
    assert obs.current_game is None


# ─── Start / Stop ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_sets_is_running():
    obs = _obs([])
    assert not obs.is_running
    await obs.start()
    assert obs.is_running
    await obs.stop()
    assert not obs.is_running


@pytest.mark.asyncio
async def test_stop_idempotent_before_start():
    obs = _obs([])
    await obs.stop()  # nie powinno rzucać


@pytest.mark.asyncio
async def test_start_idempotent():
    obs = _obs([], interval=60)
    await obs.start()
    await obs.start()  # drugi start bez efektu
    assert obs.is_running
    await obs.stop()


@pytest.mark.asyncio
async def test_loop_emits_on_game_detection():
    """Pętla async — tick wykonywany przez asyncio.sleep(0)."""
    events: List[str] = []

    async def capture(name, payload):
        events.append(payload.get("game"))

    obs = _obs(["stellaris.exe"], emit=capture, interval=1)
    await obs.start()
    await asyncio.sleep(0.15)  # daj pętli czas na 1+ tick
    await obs.stop()

    assert "Stellaris" in events


# ─── KNOWN_GAMES słownik ──────────────────────────────────────────────────────


def test_known_games_has_stellaris():
    assert "stellaris.exe" in KNOWN_GAMES
    assert KNOWN_GAMES["stellaris.exe"] == "Stellaris"


def test_known_games_has_poe2():
    assert "pathofexile2.exe" in KNOWN_GAMES


@pytest.mark.asyncio
async def test_manual_lock_skips_process_scan():
    """Ręczny profil — ignoruje brak procesu gry."""
    state = {"manual_game_profile_lock": True, "manual_game_profile_id": "stellaris"}
    obs = _obs(["chrome.exe"], state=state)
    game = await obs.tick()
    assert game == "Stellaris"
    assert obs.current_profile_id == "stellaris"
