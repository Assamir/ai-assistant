"""Perceptual hash (dHash) dla PNG — T5 / DOK observer (deduplikacja klatek)."""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image


def compute_dhash_png(png_bytes: bytes) -> int:
    """
    Difference hash 64-bit na obrazie z PNG.
    Skala 9×8 luminancja, porównania sąsiednich pikseli w poziomie (standard dHash).
    """
    with Image.open(io.BytesIO(png_bytes)) as im:
        gray = im.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        px = list(gray.getdata())

    out = 0
    bit = 0
    for row in range(8):
        base = row * 9
        for col in range(8):
            if px[base + col] > px[base + col + 1]:
                out |= 1 << bit
            bit += 1
    return out


def hamming_u64(a: int, b: int) -> int:
    """Odległość Hamminga dla dwóch 64-bitowych hashy (jako int ≥ 0)."""
    return (a ^ b).bit_count()


@dataclass
class SceneDeduper:
    """
    Pomija kolejne klatki wizualnie zbliżone do poprawnej (mała odległość dHash).
    Pierwsza klatka nigdy nie jest pomijana (aktualizacja referencji).
    """

    max_similar_distance: int = 5
    _last_hash: int | None = None

    def reset(self) -> None:
        self._last_hash = None

    def should_skip(self, png_bytes: bytes) -> bool:
        """
        True — scena zbyt podobna do poprzedniej (observer może pominąć VLM).
        False — znacząca zmiana lub pierwsza klatka; `_last_hash` uaktualnione.
        """
        h = compute_dhash_png(png_bytes)
        if self._last_hash is None:
            self._last_hash = h
            return False
        if hamming_u64(h, self._last_hash) <= self.max_similar_distance:
            return True
        self._last_hash = h
        return False


__all__ = ["SceneDeduper", "compute_dhash_png", "hamming_u64"]
