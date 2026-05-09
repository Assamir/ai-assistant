"""ObserverLoop — warunki pominięcia (DOK OBS-T-01–04), cooldown i dedup tekstu."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.ai.llm_client import ChatCompletionResult
from backend.ai.screen_capture import MINIMAL_PNG_BYTES, MockScreenCapture
from backend.ai.vision_pipeline import VisionFrameResult
from backend.config.schema import ConfigSchema
from backend.core.orchestrator import OrchestratorState
from backend.services.observer_loop import (
    ObserverLoop,
    build_observer_comment_prompt,
    process_observer_llm_response,
)


@pytest.fixture
def active_ctx() -> MagicMock:
    cfg = ConfigSchema()
    cfg.observer.vlm_timeout_seconds = 0.05
    cfg.observer.min_comment_interval_seconds = 0.0

    ctx = MagicMock()
    ctx.config = cfg
    ctx.orchestrator.state = {
        "observer_active": True,
        "current_game": "Test Game",
        "sleeping": False,
        "silent_mode": False,
    }
    ctx.orchestrator.phase = OrchestratorState.IDLE
    ctx.voice_input_coordinator = None
    ctx.game_observer = None
    ctx.screen_capture = MockScreenCapture(png_payload=MINIMAL_PNG_BYTES)
    ctx.tts_engine = None

    vp = AsyncMock()
    vp.analyze_png = AsyncMock(
        return_value=VisionFrameResult(vlm_text="ekran", ocr_text="", ocr_ran=False)
    )
    ctx.vision_pipeline = vp

    llm = AsyncMock()
    llm.chat_completion = AsyncMock(
        return_value=ChatCompletionResult(content="[EMO:happy] Coś się dzieje.")
    )
    ctx.llm_client = llm

    mgr = MagicMock()
    mgr.iter_session_ids = MagicMock(return_value=[])
    mgr.send_to_session = AsyncMock()
    ctx.websocket_manager = mgr
    ctx.game_profiles = {}
    return ctx


@pytest.mark.asyncio
async def test_obs_t01_skip_when_listening(active_ctx):
    """OBS-T-01: faza LISTENING → brak vision."""
    active_ctx.orchestrator.phase = OrchestratorState.LISTENING
    loop = ObserverLoop(active_ctx)
    await loop.run_cycle()
    active_ctx.vision_pipeline.analyze_png.assert_not_called()


@pytest.mark.asyncio
async def test_obs_t01_skip_when_backend_ptt(active_ctx):
    """OBS-T-01: backendowy PTT (`ptt_held`)."""
    coord = MagicMock()
    coord.ptt_held = True
    active_ctx.voice_input_coordinator = coord
    loop = ObserverLoop(active_ctx)
    await loop.run_cycle()
    active_ctx.vision_pipeline.analyze_png.assert_not_called()


@pytest.mark.asyncio
async def test_obs_t02_scene_deduper_skips_second_identical_frame(active_ctx):
    """Druga identyczna klatka — SceneDeduper pomija VLM (typowy przypadek)."""
    loop = ObserverLoop(active_ctx)
    await loop.run_cycle()
    active_ctx.vision_pipeline.analyze_png.assert_called()
    active_ctx.vision_pipeline.analyze_png.reset_mock()
    await loop.run_cycle()
    active_ctx.vision_pipeline.analyze_png.assert_not_called()


@pytest.mark.asyncio
async def test_obs_t02_dhash_deque_skip_fourth_when_deduper_neutral(active_ctx):
    """OBS-T-02: przy braku skipu dedupera — czwarty cykl z rzędu z tym samym dHash bez VLM."""
    loop = ObserverLoop(active_ctx)
    loop._deduper.should_skip = lambda _b: False
    for _ in range(3):
        await loop.run_cycle()
        active_ctx.vision_pipeline.analyze_png.assert_called()
        active_ctx.vision_pipeline.analyze_png.reset_mock()
    await loop.run_cycle()
    active_ctx.vision_pipeline.analyze_png.assert_not_called()


@pytest.mark.asyncio
async def test_obs_t03_vision_timeout_skips_llm(active_ctx):
    """OBS-T-03: timeout vision — bez wywołania LLM."""

    async def slow_png(_):
        import asyncio

        await asyncio.sleep(1.0)
        return VisionFrameResult(vlm_text="x", ocr_text="", ocr_ran=False)

    active_ctx.vision_pipeline.analyze_png = slow_png
    active_ctx.config.observer.vlm_timeout_seconds = 0.02

    loop = ObserverLoop(active_ctx)
    await loop.run_cycle()
    active_ctx.llm_client.chat_completion.assert_not_called()


@pytest.mark.asyncio
async def test_obs_t04_skip_no_tts_on_marker(active_ctx):
    """OBS-T-04: LLM zwraca [SKIP] — brak eventu observer_comment."""
    active_ctx.llm_client.chat_completion = AsyncMock(
        return_value=ChatCompletionResult(content="[SKIP]")
    )
    loop = ObserverLoop(active_ctx)
    await loop.run_cycle()
    for call in active_ctx.websocket_manager.send_to_session.call_args_list:
        assert call.args[1] != "observer_comment"


def test_process_observer_skip_variants():
    assert process_observer_llm_response("[SKIP]") is None
    assert process_observer_llm_response("[skip] extra") is None
    assert process_observer_llm_response("[EMO:happy] Tak.") == "[EMO:happy] Tak."


def test_comments_too_similar():
    assert ObserverLoop._comments_too_similar("To samo", ["to samo"], 0.9)
    assert not ObserverLoop._comments_too_similar("a", ["b"], 0.9)
    assert not ObserverLoop._comments_too_similar("", ["x"], 0.9)
    # returns False when recent list is empty
    assert not ObserverLoop._comments_too_similar("something", [], 0.9)
    # catches similarity against any of the last N comments
    assert ObserverLoop._comments_too_similar("To samo", ["unrelated", "to samo", "also unrelated"], 0.9)


@pytest.mark.asyncio
async def test_comment_cooldown_skips_vision(active_ctx):
    """Po komentarzu — krótki cooldown omija capture (oszczędność VLM)."""
    active_ctx.config.observer.min_comment_interval_seconds = 60.0
    loop = ObserverLoop(active_ctx)
    loop._last_comment_monotonic = 1000.0
    with patch("backend.services.observer_loop.time.monotonic", return_value=1010.0):
        await loop.run_cycle()
    active_ctx.vision_pipeline.analyze_png.assert_not_called()


@pytest.mark.asyncio
async def test_similarity_skips_emit(active_ctx):
    """Zbyt podobny tekst do poprzedniego — bez observer_comment na WS."""
    active_ctx.orchestrator.state["last_observer_comment"] = "Widzę ekran taktyczny."
    active_ctx.llm_client.chat_completion = AsyncMock(
        return_value=ChatCompletionResult(content="[EMO:neutral] Widzę ekran taktyczny.")
    )
    active_ctx.config.observer.comment_similarity_skip_threshold = 0.85
    loop = ObserverLoop(active_ctx)
    await loop.run_cycle()
    for call in active_ctx.websocket_manager.send_to_session.call_args_list:
        assert call.args[1] != "observer_comment"


@pytest.mark.asyncio
async def test_observer_paused_skips_cycle(active_ctx):
    """Stan orchestratora observer_paused — bez vision."""
    active_ctx.orchestrator.state["observer_paused"] = True
    loop = ObserverLoop(active_ctx)
    await loop.run_cycle()
    active_ctx.vision_pipeline.analyze_png.assert_not_called()


@pytest.mark.asyncio
async def test_observer_persist_sqlite(migrated_db_path):
    """Komentarz obserwatora trafia do messages (source=observer)."""
    from backend.db.repositories import MessageRepository

    cfg = ConfigSchema()
    cfg.observer.persist_observer_comments = True
    cfg.observer.min_comment_interval_seconds = 0.0

    ctx = MagicMock()
    ctx.config = cfg
    ctx.db_path = migrated_db_path
    ctx.db_session_by_ws = {}
    ctx.orchestrator.state = {
        "observer_active": True,
        "current_game": "G",
        "sleeping": False,
        "silent_mode": False,
    }
    ctx.orchestrator.phase = OrchestratorState.IDLE
    ctx.websocket_manager = MagicMock()
    ctx.websocket_manager.iter_session_ids = MagicMock(return_value=["ws-a"])
    ctx.websocket_manager.send_to_session = AsyncMock()
    ctx.llm_client = AsyncMock()
    ctx.llm_client.chat_completion = AsyncMock(
        return_value=ChatCompletionResult(content="[EMO:neutral] Komentarz testowy.")
    )
    ctx.tts_engine = None
    ctx.voice_input_coordinator = None
    ctx.game_observer = None
    ctx.game_profiles = {}

    loop = ObserverLoop(ctx)
    await loop._post_vision("G", VisionFrameResult(vlm_text="scena", ocr_text="", ocr_ran=False))

    db_sid = ctx.db_session_by_ws["ws-a"]
    rows = await MessageRepository(migrated_db_path).get_messages_for_session(db_sid)
    obs = [r for r in rows if r["source"] == "observer"]
    assert len(obs) == 1
    assert obs[0]["content"] == "Komentarz testowy."


@pytest.mark.asyncio
async def test_skip_when_game_paused_config(active_ctx):
    """skip_conditions: game_paused w stanie orchestratora."""
    active_ctx.config.observer.skip_conditions = ["game_paused"]
    active_ctx.orchestrator.state["game_paused"] = True
    loop = ObserverLoop(active_ctx)
    await loop.run_cycle()
    active_ctx.vision_pipeline.analyze_png.assert_not_called()


def test_manual_game_command_matches():
    from backend.core.command_matching import CommandMatcher

    m = CommandMatcher(fuzzy=False)
    mm = m.match_one("ustaw gre na stellaris")
    assert mm is not None
    assert mm.builtin_action == "manual_game_set"
    assert mm.params.get("game_id") == "stellaris"
