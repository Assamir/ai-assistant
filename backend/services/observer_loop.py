"""Pętla obserwatora T6: capture → dHash / SceneDeduper → VLM+OCR → LLM → TTS (DOK-08 §6)."""

from __future__ import annotations

import asyncio
import base64
import difflib
import logging
import time
from collections import deque
from typing import Any, Mapping, Optional

from backend.ai.screen_region_crop import apply_profile_crop_to_png
from backend.ai.scene_dhash import SceneDeduper, compute_dhash_png
from backend.ai.vision_pipeline import VisionFrameResult
from backend.api.app_context import AppContext, ensure_ws_db_session
from backend.core.emotion_parser import parse_emotion_tag
from backend.core.orchestrator import OrchestratorState
from backend.db.repositories import MessageRepository

_logger = logging.getLogger(__name__)


def process_observer_llm_response(response: str) -> Optional[str]:
    """None gdy [SKIP], w przeciwnym razie pełna odpowiedź (z ewentualnym tagiem EMO)."""
    stripped = response.strip()
    if not stripped:
        return None
    up = stripped.upper()
    if up == "[SKIP]" or up.startswith("[SKIP]"):
        return None
    return stripped


def build_observer_comment_prompt(
    *,
    scene_description: str,
    ocr_excerpt: str,
    last_observer_comment: str,
    game_name: str,
    game_context_prompt: str,
) -> str:
    ocr_block = f"\nOCR (fragment):\n{ocr_excerpt}\n" if ocr_excerpt.strip() else ""
    profile = game_context_prompt.strip()
    profile_block = f"\nPROFIL GRY:\n{profile}\n" if profile else ""
    return (
        "Jesteś obserwatorem gry. Właśnie przeanalizowałem ekran. Poniżej opis sceny.\n\n"
        f"SCENA: {scene_description}\n"
        f"{ocr_block}"
        f"POPRZEDNI KOMENTARZ: {last_observer_comment}\n"
        f"GRA: {game_name}\n"
        f"{profile_block}"
        "\nZASADY:\n"
        "- Skomentuj jednym zdaniem jeśli wydarzyło się coś ISTOTNEGO: rzadki drop, niebezpieczeństwo, "
        "ważna decyzja, błąd gracza.\n"
        "- Jeśli scena jest taka sama jak poprzednio lub nic ciekawego się nie dzieje — zwróć dokładnie: [SKIP]\n"
        "- Nie komentuj każdej klatki — komentuj wyjątki.\n"
        "- Zacznij od [EMO:nazwa] jeśli komentujesz.\n"
        "- Maksymalnie 2 zdania.\n"
        "- Nie zadawaj pytań — komentuj lub pomiń.\n"
    )


class ObserverLoop:
    """`capture → vision → komentarz`; warunki pominięcia i jedna aktywna iteracja naraz."""

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._in_cycle = False
        self._deduper = SceneDeduper(max_similar_distance=ctx.config.observer.scene_dhash_max_distance)
        self._dhash_window: deque[int] = deque(maxlen=3)
        self._last_game_snapshot: str | None = None
        self._last_comment_monotonic: float | None = None
        self._recent_comments: deque[str] = deque(maxlen=3)

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.get_running_loop().create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def _ensure_game_changed_reset(self, game: str | None) -> None:
        g = game or ""
        prev = self._last_game_snapshot or ""
        if g != prev:
            self._deduper.reset()
            self._dhash_window.clear()
            self._last_comment_monotonic = None
            self._recent_comments.clear()
            self._last_game_snapshot = g or None

    def _interval_seconds(self) -> float:
        st = self._ctx.orchestrator.state
        gid = st.get("current_game_profile_id")
        if isinstance(gid, str):
            prof = self._ctx.game_profiles.get(gid)
            if prof is not None and getattr(prof, "observer_interval_seconds", None) is not None:
                oi = prof.observer_interval_seconds
                if isinstance(oi, int) and oi >= 5:
                    return float(oi)
        override = st.get("observer_interval_seconds")
        if isinstance(override, int) and override >= 5:
            return float(override)
        return float(self._ctx.config.observer.cycle_interval_seconds)

    def _ptt_or_listening(self) -> bool:
        if self._ctx.orchestrator.phase == OrchestratorState.LISTENING:
            return True
        coord = getattr(self._ctx, "voice_input_coordinator", None)
        if coord is not None and getattr(coord, "ptt_held", False):
            return True
        return False

    def _should_skip_cycle(self) -> bool:
        st = self._ctx.orchestrator.state
        if not st.get("observer_active"):
            return True
        if st.get("sleeping"):
            return True
        if st.get("observer_paused"):
            return True
        game = st.get("current_game")
        if not game and self._ctx.game_observer is not None:
            game = self._ctx.game_observer.current_game
        if not game:
            return True
        if self._ptt_or_listening():
            return True
        if self._skip_from_config_conditions(st):
            return True
        return False

    def _skip_from_config_conditions(self, st: Mapping[str, Any]) -> bool:
        for key in self._ctx.config.observer.skip_conditions:
            if key == "game_paused" and st.get("game_paused"):
                return True
            if key == "low_fps" and st.get("low_fps"):
                return True
        return False

    def _comment_cooldown_active(self) -> bool:
        cfg = self._ctx.config.observer
        if cfg.min_comment_interval_seconds <= 0:
            return False
        if self._last_comment_monotonic is None:
            return False
        return (time.monotonic() - self._last_comment_monotonic) < cfg.min_comment_interval_seconds

    @staticmethod
    def _comments_too_similar(candidate: str, recent: list[str], threshold: float) -> bool:
        if threshold <= 0 or not candidate or not recent:
            return False
        cl = candidate.lower()
        return any(
            difflib.SequenceMatcher(None, cl, r.lower()).ratio() >= threshold
            for r in recent
        )

    async def _loop(self) -> None:
        while self._running:
            await asyncio.sleep(self._interval_seconds())
            if not self._running:
                break
            try:
                await self.run_cycle()
            except asyncio.CancelledError:
                raise
            except Exception:
                _logger.exception("observer loop cycle failed")

    async def run_cycle(self) -> None:
        """Pojedynczy przebieg (testy, manual)."""
        if self._in_cycle:
            return
        if self._should_skip_cycle():
            return
        if self._comment_cooldown_active():
            return
        if self._ctx.vision_pipeline is None:
            return
        cap = getattr(self._ctx, "screen_capture", None)
        if cap is None:
            return

        game = self._ctx.orchestrator.state.get("current_game")
        if not game and self._ctx.game_observer is not None:
            game = self._ctx.game_observer.current_game
        self._ensure_game_changed_reset(str(game) if game else None)

        cfg = self._ctx.config.observer
        if self._deduper.max_similar_distance != cfg.scene_dhash_max_distance:
            self._deduper = SceneDeduper(max_similar_distance=cfg.scene_dhash_max_distance)

        self._in_cycle = True
        try:
            png = await cap.capture_png(monitor_index=0)
            gid = self._ctx.orchestrator.state.get("current_game_profile_id")
            profile = (
                self._ctx.game_profiles.get(gid)
                if isinstance(gid, str)
                else None
            )
            png = apply_profile_crop_to_png(png, profile)
            h = compute_dhash_png(png)
            if len(self._dhash_window) == 3 and list(self._dhash_window).count(h) >= 3:
                return
            self._dhash_window.append(h)

            if self._deduper.should_skip(png):
                return

            vp = self._ctx.vision_pipeline
            try:
                result = await asyncio.wait_for(
                    vp.analyze_png(png),
                    timeout=cfg.vlm_timeout_seconds,
                )
            except asyncio.TimeoutError:
                _logger.info("observer: vision timeout %.1fs", cfg.vlm_timeout_seconds)
                return

            await self._post_vision(str(game) if game else None, result)
        finally:
            self._in_cycle = False

    def _game_profile_prompt(self, game_name: str) -> str:
        st = self._ctx.orchestrator.state
        gid = st.get("current_game_profile_id")
        if isinstance(gid, str):
            prof = self._ctx.game_profiles.get(gid)
            if prof is not None and getattr(prof, "context_prompt", ""):
                return str(prof.context_prompt)
        for prof in self._ctx.game_profiles.values():
            if getattr(prof, "name", None) == game_name:
                return str(getattr(prof, "context_prompt", "") or "")
        profiles = getattr(self._ctx.config, "game_profiles", None) or {}
        if isinstance(profiles, dict):
            raw = profiles.get(game_name)
            if isinstance(raw, dict):
                return str(raw.get("context_prompt") or "")
        return ""

    async def _post_vision(self, game: Optional[str], result: VisionFrameResult) -> None:
        scene = (result.vlm_text or "").strip() or "brak analizy"
        ocr_ex = (result.ocr_text or "").strip() if result.ocr_ran else ""
        st = self._ctx.orchestrator.state
        last_raw = st.get("last_observer_comment")
        last = str(last_raw).strip() if last_raw else ""
        if not last:
            last = "brak poprzedniego komentarza"
        game_name = str(game or "nieznana gra")

        prompt = build_observer_comment_prompt(
            scene_description=scene,
            ocr_excerpt=ocr_ex,
            last_observer_comment=last,
            game_name=game_name,
            game_context_prompt=self._game_profile_prompt(game_name),
        )
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        max_tok = self._ctx.config.observer.observer_comment_max_tokens
        try:
            comp = await self._ctx.llm_client.chat_completion(messages, max_tokens=max_tok)
        except Exception:
            _logger.exception("observer LLM call failed")
            return

        processed = process_observer_llm_response(comp.content or "")
        if processed is None:
            return

        emotion, spoken = parse_emotion_tag(processed)
        spoken = spoken.strip()
        if not spoken:
            return

        th = self._ctx.config.observer.comment_similarity_skip_threshold
        if self._comments_too_similar(spoken, list(self._recent_comments), th):
            return

        st["last_observer_comment"] = spoken
        self._recent_comments.append(spoken)

        await self._persist_observer_comment(spoken, emotion)

        from backend.core.notification_tone import generate_ping_wav
        from backend.core.tts_streaming import sentence_split

        mgr = self._ctx.websocket_manager
        synth = self._ctx.tts_engine
        stride = max(512, getattr(self._ctx.config.tts, "chunk_bytes", 4096))
        ping_enabled = getattr(self._ctx.config.observer, "notification_sound_enabled", True)
        ping_wav = generate_ping_wav() if ping_enabled else b""
        ping_blob = base64.standard_b64encode(ping_wav).decode("ascii") if ping_wav else ""

        for sid in mgr.iter_session_ids():
            await mgr.send_to_session(sid, "emotion", {"emotion": emotion})
            await mgr.send_to_session(
                sid,
                "observer_comment",
                {"text": spoken, "emotion": emotion, "game": game_name},
            )
            if st.get("silent_mode"):
                await mgr.send_to_session(sid, "text_overlay", {"text": spoken})
                continue
            if synth is None:
                await mgr.send_to_session(sid, "text_overlay", {"text": spoken})
                continue
            if ping_blob:
                for offset in range(0, len(ping_blob), stride):
                    await mgr.send_to_session(
                        sid,
                        "audio_stream",
                        {"chunk_base64": ping_blob[offset : offset + stride]},
                    )
            any_audio = False
            for sentence in sentence_split(spoken):
                try:
                    wav = await synth.speak(sentence, emotion=emotion or None)
                except Exception:
                    _logger.exception("observer TTS failed")
                    wav = b""
                if wav:
                    any_audio = True
                    blob = base64.standard_b64encode(wav).decode("ascii")
                    for offset in range(0, len(blob), stride):
                        await mgr.send_to_session(
                            sid,
                            "audio_stream",
                            {"chunk_base64": blob[offset : offset + stride]},
                        )
            if not any_audio:
                await mgr.send_to_session(sid, "text_overlay", {"text": spoken})

        self._last_comment_monotonic = time.monotonic()

    async def _persist_observer_comment(self, spoken: str, emotion: str) -> None:
        if not self._ctx.config.observer.persist_observer_comments:
            return
        repo = MessageRepository(self._ctx.db_path)
        done: set[int] = set()
        for ws_sid in self._ctx.websocket_manager.iter_session_ids():
            try:
                db_id = await ensure_ws_db_session(self._ctx, ws_sid)
            except Exception:
                _logger.exception("observer: ensure db session failed for ws %s", ws_sid)
                continue
            if db_id in done:
                continue
            done.add(db_id)
            try:
                await repo.create_message(db_id, "observer", spoken, emotion=emotion or None)
            except Exception:
                _logger.exception("observer: persist message failed (session_id=%s)", db_id)


__all__ = [
    "ObserverLoop",
    "build_observer_comment_prompt",
    "process_observer_llm_response",
]