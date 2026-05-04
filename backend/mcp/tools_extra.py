"""Dodatkowe narzędzia MCP: random_choice, dice_roll, format_duration."""

from __future__ import annotations

import random
from typing import Any, Dict, List

_TOOL_RANDOM_CHOICE: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "random_choice",
        "description": (
            "Losuje jeden element z podanej listy opcji. "
            "Przydatne przy podejmowaniu decyzji lub losowym wyborze."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": 'Lista opcji, np. ["atak", "obrona", "odwrót"].',
                },
            },
            "required": ["items"],
        },
    },
}

_TOOL_DICE_ROLL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "dice_roll",
        "description": "Rzuca kośćmi i zwraca wyniki z sumą. Domyślnie 1d6.",
        "parameters": {
            "type": "object",
            "properties": {
                "sides": {
                    "type": "integer",
                    "description": "Liczba ścian kości (2–100). Domyślnie 6.",
                },
                "count": {
                    "type": "integer",
                    "description": "Liczba kości do rzutu (1–20). Domyślnie 1.",
                },
            },
        },
    },
}

_TOOL_FORMAT_DURATION: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "format_duration",
        "description": (
            "Formatuje liczbę sekund jako czytelny czas (np. '1h 23m 45s'). "
            "Przydatne do cooldownów, czasu sesji lub timerów w grze."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "number",
                    "description": "Liczba sekund do sformatowania (≥ 0).",
                },
            },
            "required": ["seconds"],
        },
    },
}


def tool_random_choice(items: Any = None) -> Dict[str, Any]:
    if not isinstance(items, list) or len(items) == 0:
        return {"ok": False, "error": "items must be a non-empty list"}
    chosen = random.choice(items)
    return {"ok": True, "chosen": chosen, "count": len(items)}


def tool_dice_roll(sides: Any = 6, count: Any = 1) -> Dict[str, Any]:
    try:
        s = max(2, min(100, int(sides)))
        c = max(1, min(20, int(count)))
    except (TypeError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}
    rolls = [random.randint(1, s) for _ in range(c)]
    return {"ok": True, "rolls": rolls, "total": sum(rolls), "sides": s, "count": c}


def tool_format_duration(seconds: Any = 0) -> Dict[str, Any]:
    try:
        s = max(0, int(float(seconds)))
    except (TypeError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        fmt = f"{h}h {m:02d}m {sec:02d}s"
    elif m:
        fmt = f"{m}m {sec:02d}s"
    else:
        fmt = f"{sec}s"
    return {"ok": True, "formatted": fmt, "seconds": s}


__all__ = [
    "tool_random_choice",
    "tool_dice_roll",
    "tool_format_duration",
    "_TOOL_RANDOM_CHOICE",
    "_TOOL_DICE_ROLL",
    "_TOOL_FORMAT_DURATION",
]
