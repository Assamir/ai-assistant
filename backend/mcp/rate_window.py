"""Proste okno czasowe na limity wywołań async (np. web_search)."""

from __future__ import annotations

import asyncio
import time
from collections import deque


class AsyncRateWindow:
    """Maks. N wywołań w każdym z okien `period_seconds` (sliding)."""

    def __init__(self, max_calls: int, period_seconds: float = 60.0) -> None:
        self._max = max(1, int(max_calls))
        self._period = float(period_seconds)
        self._times: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        wait: float = 0.0
        async with self._lock:
            now = time.monotonic()
            while self._times and now - self._times[0] >= self._period:
                self._times.popleft()
            if len(self._times) < self._max:
                self._times.append(now)
                return
            wait = max(0.02, self._period - (now - self._times[0]))
        await asyncio.sleep(wait)
        await self.acquire()

    async def acquire_strict(self) -> None:
        """Jedno wywołanie w „świeżym” oknie; przy przepełnieniu — RateLimitedError (bez czekania)."""

        from backend.mcp.exceptions import RateLimitedError

        async with self._lock:
            now = time.monotonic()
            while self._times and now - self._times[0] >= self._period:
                self._times.popleft()
            if len(self._times) >= self._max:
                raise RateLimitedError("MCP: przekroczono limit wywołań w oknie czasu.")
            self._times.append(now)


__all__ = ["AsyncRateWindow"]
