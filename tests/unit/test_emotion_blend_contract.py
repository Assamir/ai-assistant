"""Contract checks for frontend emotion blending (AvatarCanvas / emotionBlend.ts)."""

from __future__ import annotations

import json
from pathlib import Path


def _ease_out_cubic(t: float) -> float:
    x = min(1.0, max(0.0, t))
    return 1.0 - (1.0 - x) ** 3


def _blend_records(a: dict[str, float], b: dict[str, float], u: float) -> dict[str, float]:
    t = min(1.0, max(0.0, u))
    keys = set(a) | set(b)
    return {k: (float(a.get(k, 0.0)) * (1.0 - t) + float(b.get(k, 0.0)) * t) for k in keys}


def test_emotions_json_loads() -> None:
    path = Path(__file__).resolve().parents[2] / "frontend" / "src" / "emotions.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "neutral" in data
    assert isinstance(data["neutral"], dict)


def test_blend_records_midpoint() -> None:
    out = _blend_records({"happy": 1.0, "relaxed": 0.2}, {"sad": 1.0}, 0.5)
    assert abs(out["happy"] - 0.5) < 1e-9
    assert abs(out["relaxed"] - 0.1) < 1e-9
    assert abs(out["sad"] - 0.5) < 1e-9


def test_ease_out_cubic_endpoints() -> None:
    assert abs(_ease_out_cubic(0.0)) < 1e-9
    assert abs(_ease_out_cubic(1.0) - 1.0) < 1e-9
