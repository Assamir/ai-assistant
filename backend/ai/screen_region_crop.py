"""Kadrowanie PNG wg `GameProfile.screen_regions` (T5)."""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING, Optional

from PIL import Image

if TYPE_CHECKING:
    from backend.services.game_profile import GameProfile

_logger = logging.getLogger(__name__)


def _dimensions(w: int, h: int, size_percent: int) -> tuple[int, int]:
    pct = max(1, min(100, size_percent))
    cw = max(8, round(w * pct / 100))
    ch = max(8, round(h * pct / 100))
    return cw, ch


def _box_for_anchor(
    w: int,
    h: int,
    cw: int,
    ch: int,
    position_raw: str,
) -> tuple[int, int, int, int]:
    pos = position_raw.strip().lower() if position_raw.strip() else "center"

    left = max(0, (w - cw) // 2)
    top = max(0, (h - ch) // 2)

    if pos in ("", "center"):
        pass
    elif pos == "top":
        top = 0
    elif pos == "bottom":
        top = max(0, h - ch)
    elif pos == "left":
        left = 0
        top = max(0, (h - ch) // 2)
    elif pos == "right":
        left = max(0, w - cw)
        top = max(0, (h - ch) // 2)
    elif pos == "top-left":
        left, top = 0, 0
    elif pos == "top-right":
        left, top = max(0, w - cw), 0
    elif pos == "bottom-left":
        left, top = 0, max(0, h - ch)
    elif pos == "bottom-right":
        left, top = max(0, w - cw), max(0, h - ch)

    left = max(0, min(left, w - cw))
    top = max(0, min(top, h - ch))
    return left, top, left + cw, top + ch


def _pick_observer_region(profile: Optional["GameProfile"]):
    if profile is None:
        return None
    regs = getattr(profile, "screen_regions", None) or []
    if not regs:
        return None
    for r in regs:
        name = getattr(r, "name", "").strip().lower()
        if name in ("observer", "viewport", "main", ""):
            return r
    return regs[0]


def apply_profile_crop_to_png(
    png: bytes,
    profile: Optional["GameProfile"],
) -> bytes:
    """Zwraca oryginał, gdy brak obszaru lub błąd PIL."""
    reg = _pick_observer_region(profile)
    if reg is None:
        return png
    try:
        img = Image.open(io.BytesIO(png))
        w, h = img.size
        cw, ch = _dimensions(w, h, int(reg.size_percent))
        box = _box_for_anchor(w, h, cw, ch, str(reg.position))
        cropped = img.crop(box).convert("RGB")
        buf = io.BytesIO()
        cropped.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as exc:
        _logger.debug("crop profile region skipped: %s", exc)
        return png


__all__ = ["apply_profile_crop_to_png"]
