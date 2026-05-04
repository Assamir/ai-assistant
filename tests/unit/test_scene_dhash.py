"""T5 — dHash + SceneDeduper."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from backend.ai.scene_dhash import SceneDeduper, compute_dhash_png, hamming_u64


def _solid_png(w: int, h: int, rgb: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), rgb).save(buf, format="PNG")
    return buf.getvalue()


def _split_halves_png(left_rgb: tuple[int, int, int], right_rgb: tuple[int, int, int]) -> bytes:
    w, h = 128, 72
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = left_rgb if x < w // 2 else right_rgb
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _gradient_png(intensity_offset: int = 0) -> bytes:
    w, h = 120, 80
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            v = min(255, max(0, (x + y) % 200 + intensity_offset))
            px[x, y] = (v, v, v)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_compute_dhash_stable_for_identical_image():
    png = _gradient_png(0)
    a = compute_dhash_png(png)
    b = compute_dhash_png(png)
    assert a == b
    assert 0 <= a < (1 << 64)


def test_similar_images_low_hamming():
    p1 = _gradient_png(0)
    p2 = _gradient_png(3)
    d = hamming_u64(compute_dhash_png(p1), compute_dhash_png(p2))
    assert d <= 12


def test_different_images_higher_hamming():
    left_right = _split_halves_png((0, 0, 0), (255, 255, 255))
    solid = _solid_png(128, 72, (128, 128, 128))
    d = hamming_u64(compute_dhash_png(left_right), compute_dhash_png(solid))
    assert d >= 8


def test_scene_deduper_first_frame_never_skipped():
    png = _solid_png(100, 100, (50, 100, 80))
    d = SceneDeduper(max_similar_distance=0)
    assert d.should_skip(png) is False


def test_scene_deduper_skips_near_duplicate():
    p1 = _gradient_png(0)
    p2 = _gradient_png(2)
    d = SceneDeduper(max_similar_distance=12)
    assert d.should_skip(p1) is False
    assert d.should_skip(p2) is True


def test_scene_deduper_detects_change():
    d = SceneDeduper(max_similar_distance=4)
    a = _split_halves_png((0, 0, 0), (0, 0, 0))
    b = _split_halves_png((0, 0, 0), (255, 255, 255))
    assert d.should_skip(a) is False
    assert d.should_skip(b) is False


@pytest.mark.asyncio
async def test_dhash_works_on_minimal_png_from_screen_capture():
    from backend.ai.screen_capture import MINIMAL_PNG_BYTES

    h = compute_dhash_png(MINIMAL_PNG_BYTES)
    assert isinstance(h, int)
