"""VLM + LLM: dopasowanie profilu gry gdy psutil nic nie znalazł (OBSERVER_SPEC §2.2)."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from backend.api.app_context import AppContext

_logger = logging.getLogger(__name__)


def _parse_profile_token(raw: str, ctx: AppContext) -> Optional[Tuple[str, Optional[str]]]:
    t = raw.strip().lower()
    t = t.strip("`\"'")
    if not t or t in ("none", "unknown", "brak", "null", "n/a"):
        return None
    profiles = ctx.game_profiles
    if t in profiles:
        p = profiles[t]
        return (p.name, p.id)
    # czasem model zwraca "id: stellaris"
    m = re.search(r"([a-z0-9][a-z0-9_.-]{0,63})", t, re.I)
    if m:
        cand = m.group(1).lower()
        if cand in profiles:
            p = profiles[cand]
            return (p.name, p.id)
    return None


async def probe_game_identity_from_screen(ctx: AppContext) -> Optional[Tuple[str, Optional[str]]]:
    if not ctx.config.observer.vlm_fallback_game_detection:
        return None
    if not ctx.config.vlm.enabled or ctx.vlm_engine is None:
        return None
    if ctx.vision_pipeline is None or ctx.screen_capture is None:
        return None

    try:
        png = await ctx.screen_capture.capture_png(monitor_index=0)
    except Exception as exc:
        _logger.debug("vlm game probe: capture failed: %s", exc)
        return None

    timeout = float(ctx.config.observer.vlm_timeout_seconds)
    try:
        result = await asyncio.wait_for(ctx.vision_pipeline.analyze_png(png), timeout=timeout)
    except asyncio.TimeoutError:
        _logger.debug("vlm game probe: vision timeout")
        return None
    except Exception as exc:
        _logger.debug("vlm game probe: vision error: %s", exc)
        return None

    caption = (result.vlm_text or "").strip()
    if not caption:
        return None

    items = sorted(ctx.game_profiles.items(), key=lambda kv: kv[0])[:64]
    lines = [f"- {pid}: {getattr(prof, 'name', pid)}" for pid, prof in items]
    catalog = "\n".join(lines)
    prompt = (
        "Z mapy poniżej wybierz DOKŁADNIE JEDEN identyfikator gry (lewa kolumna przed dwukropkiem), "
        "który najlepiej pasuje do tego, co widać na ekranie wg opisu.\n"
        "Jeśli żaden nie pasuje — odpowiedz NONE.\n\n"
        f"Mapa profili:\n{catalog}\n\n"
        f"Opis ekranu (VLM):\n{caption}\n\n"
        "Odpowiedz jednym tokenem: identyfikator lub NONE."
    )
    try:
        comp = await ctx.llm_client.chat_completion(
            [{"role": "user", "content": prompt}],
            max_tokens=32,
        )
    except Exception as exc:
        _logger.debug("vlm game probe: llm error: %s", exc)
        return None

    token = (comp.content or "").strip()
    return _parse_profile_token(token, ctx)


__all__ = ["probe_game_identity_from_screen"]
