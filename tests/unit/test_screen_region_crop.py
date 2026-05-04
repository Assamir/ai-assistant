"""Kadrowanie PNG wg profilu gry."""

from __future__ import annotations

import io

from PIL import Image

from backend.ai.screen_region_crop import apply_profile_crop_to_png
from backend.services.game_profile import GameProfile, ScreenRegion


def _solid_png(rgb: tuple[int, int, int]) -> bytes:
    img = Image.new("RGB", (100, 80), rgb)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_crop_center_reduces_dimensions():
    prof = GameProfile(
        id="t",
        name="T",
        screen_regions=[
            ScreenRegion(name="observer", position="center", size_percent=50),
        ],
    )
    png = _solid_png((200, 0, 0))
    out = apply_profile_crop_to_png(png, prof)
    cropped = Image.open(io.BytesIO(out))
    assert cropped.size == (50, 40)


def test_no_regions_returns_original():
    prof = GameProfile(id="x", name="X")
    png = _solid_png((0, 255, 0))
    assert apply_profile_crop_to_png(png, prof) == png
