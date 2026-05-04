"""Mapowanie emocji → parametry TTS (speed ×, pitch %) wg docs/EMOTION_SPEC.md §10."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

# EMOTION_SPEC.md §10 — Piper speed / pitch_percent
_EMOTION_TTS: Dict[str, Tuple[float, float]] = {
    "neutral": (1.0, 0.0),
    "happy": (1.1, 5.0),
    "amused": (1.05, 3.0),
    "proud": (1.0, -2.0),
    "sympathetic": (0.9, -3.0),
    "sad": (0.8, -5.0),
    "disappointed": (0.85, -4.0),
    "angry": (1.1, 8.0),
    "disgusted": (0.95, -2.0),
    "excited": (1.2, 10.0),
    "scared": (1.3, 15.0),
    "surprised": (1.25, 12.0),
    "nervous": (1.2, 5.0),
    "thinking": (0.85, -2.0),
    "confused": (0.9, 2.0),
    "nostalgic": (0.8, -2.0),
    "sarcastic": (0.9, -3.0),
}


def emotion_speed_pitch(emotion: Optional[str]) -> Tuple[float, float]:
    """Zwraca (speed_multiplier, pitch_percent). Nieznana emocja → neutral."""
    if not emotion:
        return _EMOTION_TTS["neutral"]
    key = emotion.strip().lower()
    return _EMOTION_TTS.get(key, _EMOTION_TTS["neutral"])


def combined_speed(cfg_voice_speed: float, emotion: Optional[str]) -> float:
    em_speed, _ = emotion_speed_pitch(emotion)
    return float(max(0.25, min(3.0, cfg_voice_speed * em_speed)))


def length_scale_from_speed(combined_speed: float) -> float:
    """Piper: większy length_scale ≈ wolniej — odwrotność efektywnej szybkości."""
    scale = 1.0 / combined_speed
    return float(max(0.35, min(3.0, scale)))


__all__ = ["emotion_speed_pitch", "combined_speed", "length_scale_from_speed"]
