"""Detekcja uruchomionych gier i pętla obserwacji (ObserverConfig §4)."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional

from backend.config.schema import ObserverConfig

EmitFn = Callable[[str, Mapping[str, Any]], Awaitable[None]]

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
    ) -> None:
        self._cfg = config
        self._emit = emitter
        self._task: Optional[asyncio.Task[None]] = None
        self._current_game: Optional[str] = None
        self._running = False

    def update_observer_config(self, config: ObserverConfig) -> None:
        """Hot-reload: nowy ObserverConfig (np. interwał)."""
        self._cfg = config

    # ── publiczne właściwości ────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_game(self) -> Optional[str]:
        return self._current_game

    # ── API start/stop ───────────────────────────────────────────────────────

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

    # ── detekcja ─────────────────────────────────────────────────────────────

    def _list_processes(self) -> List[str]:
        """Zwraca nazwy bieżących procesów (wymaga psutil; bez niego → [])."""
        try:
            import psutil  # type: ignore[import-not-found]
            return [p.info["name"] or "" for p in psutil.process_iter(["name"])]
        except ImportError:
            return []
        except Exception:
            return []

    def _detect_game(self, process_names: List[str]) -> Optional[str]:
        """Dopasowuje nazwy procesów do słownika znanych gier (case-insensitive)."""
        for name in process_names:
            game = KNOWN_GAMES.get(name.lower())
            if game:
                return game
        return None

    # ── jeden tick ───────────────────────────────────────────────────────────

    async def tick(self) -> Optional[str]:
        """
        Wykonuje jeden cykl detekcji.
        Emituje 'game_detected' gdy stan się zmienił.
        Zwraca aktualnie wykrytą grę (lub None).
        """
        names = await asyncio.to_thread(self._list_processes)
        game = self._detect_game(names)

        if game != self._current_game:
            self._current_game = game
            if self._emit is not None:
                await self._emit(
                    "game_detected",
                    {"game": game, "active": game is not None},
                )

        return self._current_game

    # ── pętla wewnętrzna ─────────────────────────────────────────────────────

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.tick()
            except Exception:
                pass
            await asyncio.sleep(self._cfg.check_interval_seconds)


__all__ = ["GameObserver", "KNOWN_GAMES"]
