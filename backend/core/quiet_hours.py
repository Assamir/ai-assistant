"""Cisza nocna — okno czasowe z obsługą przekroczenia północy (czas lokalny)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.config.schema import ConfigSchema

_HHMM = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*$")


def parse_hhmm_to_minutes(value: str) -> int | None:
    """Zwraca minuty od północy [0, 1439] lub None gdy nieprawidłowy format."""
    m = _HHMM.match(value or "")
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        return None
    return h * 60 + mi


def is_quiet_hours_now(*, start: str, end: str, when: datetime | None = None) -> bool:
    """
    True gdy bieżący czas lokalny wpada w [start, end) z obsługą okna przez północ
    (np. 23:00–07:00 → aktywne od 23:00 do 06:59:59).
    """
    sm = parse_hhmm_to_minutes(start)
    em = parse_hhmm_to_minutes(end)
    if sm is None or em is None:
        return False
    now = when or datetime.now().astimezone()
    cur = now.hour * 60 + now.minute
    if sm < em:
        return sm <= cur < em
    if sm > em:
        return cur >= sm or cur < em
    return False


def quiet_hours_suppresses_voice(cfg: ConfigSchema, when: datetime | None = None) -> bool:
    """Czy na podstawie konfiguracji należy wyciszyć TTS (głos asystenta / obserwatora)."""
    if not getattr(cfg, "quiet_hours_enabled", False):
        return False
    return is_quiet_hours_now(start=cfg.quiet_hours_start, end=cfg.quiet_hours_end, when=when)


__all__ = ["is_quiet_hours_now", "parse_hhmm_to_minutes", "quiet_hours_suppresses_voice"]
