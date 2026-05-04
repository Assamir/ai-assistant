"""Detekcja uruchomionych gier i pętla obserwacji (ObserverConfig §4)."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Dict, List, Mapping, MutableMapping, Optional, Tuple

from backend.config.schema import ObserverConfig

EmitFn = Callable[[str, Mapping[str, Any]], Awaitable[None]]
VlmGameFallbackFn = Callable[[], Awaitable[Optional[Tuple[str, Optional[str]]]]]

KNOWN_GAMES: Dict[str, str] = {
    "stellaris.exe": "Stellaris",
    "pathofexile2.exe": "Path of Exile 2",
    "pathofexile.exe": "Path of Exile",
    "diablo iv.exe": "Diablo IV",
    "cyberpunk2077.exe": "Cyberpunk 2077",
    "baldursgate3.exe": "Baldur's Gate 3",
    "witcher3.exe": "The Witcher 3",
}


class GameObserver:
    """Async obserwator: co `check_interval_seconds` sek. sprawdza procesy i emituje zdarzenia."""

    def __init__(
        self,
        config: ObserverConfig,
        *,
        emitter: Optional[EmitFn] = None,
        orchestrator_state: Optional[MutableMapping[str, Any]] = None,
        profiles_by_id: Optional[Mapping[str, Any]] = None,
        vlm_fallback_fn: Optional[VlmGameFallbackFn] = None,
    ) -> None:
        self._cfg = config
        self._emit = emitter
        self._state = orchestrator_state
        self._profiles: Dict[str, Any] = dict(profiles_by_id or {})
        self._task: Optional[asyncio.Task[None]] = None
        self._current_game: Optional[str] = None
        self._current_profile_id: Optional[str] = None
        self._running = False
        self._vlm_fallback_fn = vlm_fallback_fn
        self._last_vlm_attempt_mono: Optional[float] = None

    def set_vlm_fallback(self, fn: Optional[VlmGameFallbackFn]) -> None:
        self._vlm_fallback_fn = fn

    def set_profiles(self, profiles_by_id: Mapping[str, Any]) -> None:
        """Hot-reload / start: nowy indeks profili."""
        self._profiles = dict(profiles_by_id)

    def update_observer_config(self, config: ObserverConfig) -> None:
        """Hot-reload: nowy ObserverConfig (np. interwał)."""
        self._cfg = config

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_game(self) -> Optional[str]:
        return self._current_game

    @property
    def current_profile_id(self) -> Optional[str]:
        return self._current_profile_id

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

    def _list_processes(self) -> List[str]:
        """Zwraca nazwy bieżących procesów (wymaga psutil; bez niego → [])."""
        try:
            import psutil  # type: ignore[import-not-found]
            return [p.info["name"] or "" for p in psutil.process_iter(["name"])]
        except ImportError:
            return []
        except Exception:
            return []

    def _detect_from_profiles(self, norm_names: List[str]) -> Optional[Any]:
        """Pierwszy profil z listy `process_names` zawartych w uruchomionych procesach (kolejność po id)."""
        lower = {n.lower() for n in norm_names if n}
        if not lower or not self._profiles:
            return None
        for pid in sorted(self._profiles.keys()):
            prof = self._profiles[pid]
            for proc in getattr(prof, "process_names", []) or []:
                pl = proc.lower()
                if pl in lower:
                    return prof
        return None

    def _detect_game_legacy(self, process_names: List[str]) -> Optional[str]:
        for name in process_names:
            game = KNOWN_GAMES.get(name.lower())
            if game:
                return game
        return None

    def _resolve_detection(
        self, process_names: List[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Zwraca (nazwa_wyświetlana, profile_id)."""
        if self._state and self._state.get("manual_game_profile_lock"):
            mid = self._state.get("manual_game_profile_id")
            if isinstance(mid, str) and mid in self._profiles:
                prof = self._profiles[mid]
                return prof.name, prof.id
            if isinstance(mid, str) and mid not in self._profiles:
                _ = mid  # nieznany id — spróbuj procesów

        prof = self._detect_from_profiles(process_names)
        if prof is not None:
            return prof.name, prof.id

        legacy = self._detect_game_legacy(process_names)
        if legacy is None:
            return None, None
        for pid, p in self._profiles.items():
            if p.name == legacy:
                return legacy, pid
        return legacy, None

    async def tick(self) -> Optional[str]:
        """
        Wykonuje jeden cykl detekcji.
        Emituje 'game_detected' gdy stan się zmienił.
        Zwraca aktualnie wykrytą grę (lub None).
        """
        names = await asyncio.to_thread(self._list_processes)
        game, gid = self._resolve_detection(names)

        locked = bool(self._state and self._state.get("manual_game_profile_lock"))

        if (
            game is None
            and not locked
            and self._cfg.vlm_fallback_game_detection
            and self._vlm_fallback_fn is not None
            and (
                self._last_vlm_attempt_mono is None
                or (
                    time.monotonic() - self._last_vlm_attempt_mono
                    >= float(self._cfg.vlm_fallback_min_interval_seconds)
                )
            )
        ):
            self._last_vlm_attempt_mono = time.monotonic()
            try:
                vlm_pick = await self._vlm_fallback_fn()
            except Exception:
                vlm_pick = None
            if isinstance(vlm_pick, tuple) and len(vlm_pick) == 2:
                g2, gid2 = vlm_pick
                if isinstance(g2, str) and g2.strip():
                    game, gid = g2.strip(), gid2 if isinstance(gid2, str) else None

        changed = game != self._current_game or gid != self._current_profile_id
        if changed:
            self._current_game = game
            self._current_profile_id = gid
            if self._emit is not None:
                await self._emit(
                    "game_detected",
                    {
                        "game": game,
                        "game_id": gid,
                        "active": game is not None,
                    },
                )

        return self._current_game

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.tick()
            except Exception:
                pass
            await asyncio.sleep(self._cfg.check_interval_seconds)


__all__ = ["GameObserver", "KNOWN_GAMES"]
