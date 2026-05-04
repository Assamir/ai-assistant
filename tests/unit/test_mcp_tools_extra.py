"""Narzędzia MCP extra: random_choice, dice_roll, format_duration."""

from __future__ import annotations

import pytest

from backend.mcp.registry import build_default_tool_registry
from backend.mcp.tools_extra import tool_dice_roll, tool_format_duration, tool_random_choice


# ─── random_choice ────────────────────────────────────────────────────────────


def test_random_choice_returns_item_from_list():
    items = ["atak", "obrona", "odwrót"]
    res = tool_random_choice(items=items)
    assert res["ok"] is True
    assert res["chosen"] in items
    assert res["count"] == 3


def test_random_choice_single_item_always_returns_it():
    res = tool_random_choice(items=["jedyna"])
    assert res["ok"] is True
    assert res["chosen"] == "jedyna"


def test_random_choice_empty_list_error():
    res = tool_random_choice(items=[])
    assert res["ok"] is False
    assert "error" in res


def test_random_choice_non_list_error():
    res = tool_random_choice(items=None)
    assert res["ok"] is False


def test_random_choice_distribution_covers_all(monkeypatch):
    """Przy 100 losowaniach z listy 3 elementów każdy pojawi się ≥ raz."""
    items = ["a", "b", "c"]
    seen = set()
    for _ in range(100):
        r = tool_random_choice(items=items)
        seen.add(r["chosen"])
    assert seen == {"a", "b", "c"}


# ─── dice_roll ────────────────────────────────────────────────────────────────


def test_dice_roll_default_d6():
    res = tool_dice_roll()
    assert res["ok"] is True
    assert res["sides"] == 6
    assert res["count"] == 1
    assert len(res["rolls"]) == 1
    assert 1 <= res["rolls"][0] <= 6
    assert res["total"] == res["rolls"][0]


def test_dice_roll_multi_dice():
    res = tool_dice_roll(sides=20, count=3)
    assert res["ok"] is True
    assert len(res["rolls"]) == 3
    assert res["total"] == sum(res["rolls"])
    for r in res["rolls"]:
        assert 1 <= r <= 20


def test_dice_roll_clamps_sides_min():
    res = tool_dice_roll(sides=1)
    assert res["sides"] == 2


def test_dice_roll_clamps_sides_max():
    res = tool_dice_roll(sides=999)
    assert res["sides"] == 100


def test_dice_roll_clamps_count_min():
    res = tool_dice_roll(count=0)
    assert res["count"] == 1
    assert len(res["rolls"]) == 1


def test_dice_roll_clamps_count_max():
    res = tool_dice_roll(count=99)
    assert res["count"] == 20
    assert len(res["rolls"]) == 20


def test_dice_roll_d1_always_lands_on_1():
    # sides=1 → clamp → 2, ale upewniamy się że wynik jest w zakresie
    res = tool_dice_roll(sides=2, count=5)
    for r in res["rolls"]:
        assert r in (1, 2)


# ─── format_duration ─────────────────────────────────────────────────────────


def test_format_duration_seconds_only():
    res = tool_format_duration(seconds=45)
    assert res["ok"] is True
    assert res["formatted"] == "45s"
    assert res["seconds"] == 45


def test_format_duration_minutes():
    res = tool_format_duration(seconds=90)
    assert res["formatted"] == "1m 30s"


def test_format_duration_exact_minute():
    res = tool_format_duration(seconds=60)
    assert res["formatted"] == "1m 00s"


def test_format_duration_hours():
    res = tool_format_duration(seconds=3661)
    assert res["formatted"] == "1h 01m 01s"


def test_format_duration_zero():
    res = tool_format_duration(seconds=0)
    assert res["formatted"] == "0s"


def test_format_duration_negative_clamped_to_zero():
    res = tool_format_duration(seconds=-5)
    assert res["seconds"] == 0
    assert res["formatted"] == "0s"


def test_format_duration_float_input():
    res = tool_format_duration(seconds=3.9)
    assert res["seconds"] == 3
    assert res["formatted"] == "3s"


def test_format_duration_large_value():
    res = tool_format_duration(seconds=7200)
    assert res["formatted"] == "2h 00m 00s"


# ─── Integracja z rejestrem ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_all_extra_tools_registered():
    """random_choice, dice_roll, format_duration są w domyślnym rejestrze."""
    reg = build_default_tool_registry()
    names = {t["function"]["name"] for t in reg.openai_tools()}
    assert "random_choice" in names
    assert "dice_roll" in names
    assert "format_duration" in names


@pytest.mark.asyncio
async def test_random_choice_via_registry():
    reg = build_default_tool_registry()
    res = await reg.invoke("random_choice", {"items": ["x", "y"]})
    assert res["ok"] is True
    assert res["chosen"] in ("x", "y")


@pytest.mark.asyncio
async def test_dice_roll_via_registry():
    reg = build_default_tool_registry()
    res = await reg.invoke("dice_roll", {"sides": 10, "count": 2})
    assert res["ok"] is True
    assert len(res["rolls"]) == 2


@pytest.mark.asyncio
async def test_format_duration_via_registry():
    reg = build_default_tool_registry()
    res = await reg.invoke("format_duration", {"seconds": 125})
    assert res["ok"] is True
    assert res["formatted"] == "2m 05s"


@pytest.mark.asyncio
async def test_openai_tool_dispatch_random_choice():
    """invoke_openai_tool_call obsługuje random_choice przez blob OpenAI."""
    reg = build_default_tool_registry()
    import json
    blob = {
        "id": "rc-1",
        "type": "function",
        "function": {"name": "random_choice", "arguments": json.dumps({"items": ["tak", "nie"]})},
    }
    msg = await reg.invoke_openai_tool_call(blob)
    assert msg["role"] == "tool"
    assert msg["tool_call_id"] == "rc-1"
    result = json.loads(msg["content"])
    assert result["chosen"] in ("tak", "nie")
