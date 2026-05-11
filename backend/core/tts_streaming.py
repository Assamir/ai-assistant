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

# --- Markdown → plain text (dla TTS) ----------------------------------------
_MD_CODE_FENCE = re.compile(r"```[^`]*```", re.DOTALL)
_MD_CODE_INLINE = re.compile(r"`([^`]+)`")
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MD_IMG = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
_MD_BOLD_STAR = re.compile(r"\*\*([^*\n]+?)\*\*")
_MD_BOLD_UNDER = re.compile(r"__([^_\n]+?)__")
_MD_ITALIC_STAR = re.compile(r"(?<!\*)\*([^*\n]+?)\*(?!\*)")
_MD_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_MD_LIST_BULLET = re.compile(r"^[ \t]*[-*+][ \t]+", re.MULTILINE)
_MD_BLOCKQUOTE = re.compile(r"^>\s?", re.MULTILINE)
_MD_HR = re.compile(r"^[ \t]*[-*_]{3,}[ \t]*$", re.MULTILINE)
_DOUBLE_NL = re.compile(r"\n[ \t]*\n+")
_SINGLE_NL = re.compile(r"\n+")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_BARE_URL = re.compile(r"https?://\S+")


def strip_markdown_for_tts(text: str) -> str:
    """Usuń markdown który źle brzmi w TTS (gwiazdki, linki, nagłówki, code, listy).

    Zachowuje strukturę zdań: `\\n\\n` → ". " (kropka jako pauza między akapitami),
    pojedyncze `\\n` → spacja.
    """
    if not text:
        return text
    t = text
    t = _MD_CODE_FENCE.sub("", t)
    t = _MD_IMG.sub(r"\1", t)
    t = _MD_LINK.sub(r"\1", t)
    t = _MD_CODE_INLINE.sub(r"\1", t)
    t = _MD_BOLD_STAR.sub(r"\1", t)
    t = _MD_BOLD_UNDER.sub(r"\1", t)
    t = _MD_ITALIC_STAR.sub(r"\1", t)
    t = _MD_HEADING.sub("", t)
    t = _MD_LIST_BULLET.sub("", t)
    t = _MD_BLOCKQUOTE.sub("", t)
    t = _MD_HR.sub("", t)
    t = _BARE_URL.sub("", t)  # gołe URL-e nie nadają się do czytania
    t = _DOUBLE_NL.sub(". ", t)
    t = _SINGLE_NL.sub(" ", t)
    t = _MULTI_SPACE.sub(" ", t)
    # Zwiń `: .` → `:` i `. .` → `.` które mogą powstać po wymianach
    t = re.sub(r":\s*\.\s*", ". ", t)
    t = re.sub(r"\.\s*\.+", ".", t)
    return t.strip()


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
