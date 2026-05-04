"""Pauza / wznowienie pętli obserwatora (OBSERVER_SPEC / T6 dzień 5)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from backend.api.app_context import AppContext


class ObserverPauseManager:
    """Prosty manager stanu `observer_paused` z opcjonalnym opóźnieniem wznowienia."""

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx

    async def pause(self) -> None:
        self._ctx.orchestrator.state["observer_paused"] = True

    async def resume(self, *, grace_seconds: float = 2.0) -> None:
        if grace_seconds > 0:
            await asyncio.sleep(grace_seconds)
        st = self._ctx.orchestrator.state
        if not st.get("sleeping"):
            st["observer_paused"] = False


__all__ = ["ObserverPauseManager"]
