"""Czyszczenie transkrypcji STT — m.in. prefiks „Hej Aria” przed wysłaniem do LLM."""

from __future__ import annotations

import re


def strip_wake_prefixes(text: str, prefixes: list[str]) -> str:
    """
    Usuwa wiodącą frazę (np. wakeword po polsku) jeśli transkrypt zaczyna się od niej.

    Dopasowanie bez rozróżniania wielkości liter; po frazie opcjonalnie przecinek/myślnik/spacje.
    """
    t = text.strip()
    if not t or not prefixes:
        return t

    ordered = sorted({p.strip() for p in prefixes if p and str(p).strip()}, key=len, reverse=True)
    for raw in ordered:
        pat = "^" + re.escape(raw) + r"[\s,;:\-\u2014]*"
        m = re.match(pat, t, re.IGNORECASE)
        if m:
            return t[m.end() :].strip()
    return t


__all__ = ["strip_wake_prefixes"]
