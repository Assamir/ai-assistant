"""Testy ciszy nocnej (quiet hours)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.config.schema import ConfigSchema
from backend.core.quiet_hours import is_quiet_hours_now, parse_hhmm_to_minutes, quiet_hours_suppresses_voice

_TZ_TEST = timezone(timedelta(hours=2))  # stały offset (bez bazy tzdata IANA na Windows)


def test_parse_hhmm():
    assert parse_hhmm_to_minutes("23:00") == 23 * 60
    assert parse_hhmm_to_minutes("07:30") == 7 * 60 + 30
    assert parse_hhmm_to_minutes("bad") is None
    assert parse_hhmm_to_minutes("25:00") is None


@pytest.mark.parametrize(
    ("start", "end", "when", "expected"),
    [
        ("09:00", "17:00", datetime(2026, 5, 9, 12, 0, tzinfo=_TZ_TEST), True),
        ("09:00", "17:00", datetime(2026, 5, 9, 8, 0, tzinfo=_TZ_TEST), False),
        ("23:00", "07:00", datetime(2026, 5, 9, 23, 30, tzinfo=_TZ_TEST), True),
        ("23:00", "07:00", datetime(2026, 5, 9, 3, 0, tzinfo=_TZ_TEST), True),
        ("23:00", "07:00", datetime(2026, 5, 9, 12, 0, tzinfo=_TZ_TEST), False),
    ],
)
def test_is_quiet_hours_window(start: str, end: str, when: datetime, expected: bool):
    assert is_quiet_hours_now(start=start, end=end, when=when) is expected


def test_quiet_hours_suppresses_only_when_enabled():
    cfg = ConfigSchema()
    assert cfg.quiet_hours_enabled is False
    assert quiet_hours_suppresses_voice(cfg) is False

    cfg2 = ConfigSchema.model_validate(
        {
            "quiet_hours_enabled": True,
            "quiet_hours_start": "23:00",
            "quiet_hours_end": "07:00",
        }
    )
    when_inside = datetime(2026, 5, 9, 2, 0, tzinfo=_TZ_TEST)
    assert quiet_hours_suppresses_voice(cfg2, when=when_inside) is True
    when_out = datetime(2026, 5, 9, 12, 0, tzinfo=_TZ_TEST)
    assert quiet_hours_suppresses_voice(cfg2, when=when_out) is False
