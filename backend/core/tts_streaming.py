"""Sentence-level splitting for incremental TTS synthesis (F-AI-05)."""

from __future__ import annotations

import re
from typing import List

_ABBREV = frozenset([
    "dr", "mgr", "inż", "prof", "hab", "np", "tzn", "tzw", "itd", "itp",
    "nr", "ok", "m", "km", "cm", "mm", "kg", "g", "ml", "vs", "etc",
    "mr", "mrs", "ms", "st", "pt", "ul", "al",
])

_SPLIT = re.compile(r"(?<=[.!?])\s+")
_TRAIL_WORD = re.compile(r"\b(\w+)\.$")


def sentence_split(text: str, min_len: int = 30) -> List[str]:
    """Split *text* into sentence-sized chunks for per-sentence TTS calls.

    Rules:
    - Split after ``.!?`` followed by whitespace.
    - Do NOT split after known abbreviations (dr., np., itd. …).
    - Merge segments shorter than *min_len* chars into the following one so
      very short fragments (e.g. "Tak!") don't cause extra TTS round-trips.
    """
    text = text.strip()
    if not text:
        return []

    parts = _SPLIT.split(text)
    result: List[str] = []

    for part in parts:
        if not result:
            result.append(part)
            continue
        prev = result[-1]
        m = _TRAIL_WORD.search(prev)
        is_abbrev = bool(m and m.group(1).lower() in _ABBREV)
        if len(prev) < min_len or is_abbrev:
            result[-1] = prev + " " + part
        else:
            result.append(part)

    return [s.strip() for s in result if s.strip()]
