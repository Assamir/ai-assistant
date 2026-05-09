"""Monitor trybu online — ping TCP 1.1.1.1:53 co 30s, aktualizuje orchestrator.state["online"]."""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any, Awaitable, Callable, Dict, MutableMapping, Optional

_logger = logging.getLogger(__name__)

_CHECK_HOST = "1.1.1.1"
_CHECK_PORT = 53
_CHECK_TIMEOUT = 3.0

BroadcastFn = Callable[[str, Dict[str, Any]], Awaitable[None]]


def _tcp_probe() -> bool:
    """Synchronous TCP probe — wywołuj przez run_in_executor."""
    try:
        with socket.create_connection((_CHECK_HOST, _CHECK_PORT), timeout=_CHECK_TIMEOUT):
            return True
    except OSError:
        return False


class OnlineMonitor:
    """Pętla w tle: sprawdza połączenie TCP co interval_s sekund.

    Aktualizuje state["online"] i emituje system_state gdy status się zmienia.
    """

    def __init__(
        self,
        state: MutableMapping[str, Any],
        *,
        broadcast_fn: Optional[BroadcastFn] = None,
        interval_seconds: float = 30.0,
    ) -> None:
        self._state = state
        self._broadcast = broadcast_fn
        self._interval = interval_seconds
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        await self._tick()
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval)
                break
            except asyncio.TimeoutError:
                pass
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                _logger.exception("OnlineMonitor tick failed")

    async def _tick(self) -> None:
        loop = asyncio.get_running_loop()
        was_online: bool = bool(self._state.get("online", True))
        is_online: bool = await loop.run_in_executor(None, _tcp_probe)
        self._state["online"] = is_online

        if is_online != was_online:
            status = "online" if is_online else "offline"
            _logger.info("Tryb online zmieniony: %s", status)
            if self._broadcast:
                await self._broadcast(
                    "system_state",
                    {"state": status, "health": "ok" if is_online else "degraded"},
                )


__all__ = ["OnlineMonitor", "_tcp_probe"]
