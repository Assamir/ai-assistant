"""Parser tagów [EMO:...] — DOK-06 §8."""

from __future__ import annotations

import logging
import re
from typing import Optional

_logger = logging.getLogger(__name__)

EMOTION_TAG_PATTERN = re.compile(r"^\[EMO:([a-z_]+)\]\s*", re.IGNORECASE)

VALID_EMOTIONS = frozenset(
    [
        "happy",
        "amused",
        "proud",
        "sympathetic",
        "sad",
        "disappointed",
        "angry",
        "disgusted",
        "excited",
        "scared",
        "surprised",
        "nervous",
        "thinking",
        "confused",
        "nostalgic",
        "sarcastic",
        "neutral",
    ]
)


def parse_emotion_tag(text: str) -> tuple[str, str]:
    """
    Zwraca (emotion_name, text_without_tag).
    Fallback: ("neutral", original_text) gdy brak lub nieznana emocja.
    """
    match = EMOTION_TAG_PATTERN.match(text)
    if not match:
        return "neutral", text

    emotion = match.group(1).lower()
    remaining = text[match.end() :]

    if emotion not in VALID_EMOTIONS:
        _logger.warning("unknown EMO tag %r — fallback neutral", emotion)
        return "neutral", remaining

    return emotion, remaining


def resolve_default_emotion(
    parsed_emotion: Optional[str],
    persona_bias: str,
    system_state: str,
) -> str:
    """Priorytet: LLM tag (non-neutral) > system_state > persona_bias > neutral."""
    if parsed_emotion and parsed_emotion != "neutral":
        return parsed_emotion

    state_forced = {
        "error": "sad",
        "degraded": "sad",
    }
    if system_state in state_forced:
        return state_forced[system_state]

    return persona_bias if persona_bias else "neutral"


__all__ = [
    "EMOTION_TAG_PATTERN",
    "VALID_EMOTIONS",
    "parse_emotion_tag",
    "resolve_default_emotion",
]
