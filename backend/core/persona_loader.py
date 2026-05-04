"""Ładowanie person z plików personas/{name}.md — DOK-05 §2."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field


class PersonaFrontmatter(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9_-]+$")
    display_name: str
    version: str = "1.0"
    proactivity: Literal["passive", "moderate", "active"] = "moderate"
    tts_emotion_bias: str = "neutral"
    emotion_bias: dict[str, float] = Field(default_factory=dict)


@dataclass(frozen=True)
class LoadedPersona:
    persona_id: str
    frontmatter: PersonaFrontmatter
    body_markdown: str


_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(?P<meta>.*?)\n---\s*\n(?P<body>.*)$",
    re.DOTALL | re.MULTILINE,
)


class PersonaLoader:
    """Odczyt YAML frontmatter + treść markdown z personas/."""

    def __init__(self, personas_dir: str | Path) -> None:
        self._dir = Path(personas_dir)

    def load(self, persona_name: str) -> LoadedPersona:
        path = self._dir / f"{persona_name}.md"
        raw = path.read_text(encoding="utf-8")
        return self.loads(raw, persona_name=persona_name, source_hint=str(path))

    def loads(self, raw: str, *, persona_name: str, source_hint: str = "") -> LoadedPersona:
        m = _FRONTMATTER_RE.match(raw.strip())
        if not m:
            raise ValueError(
                f"Persona {persona_name!r} ({source_hint}): brak prawidłowego frontmatter ---"
            )
        meta_yaml = yaml.safe_load(m.group("meta")) or {}
        fm = PersonaFrontmatter.model_validate(meta_yaml)
        body = m.group("body").strip()
        return LoadedPersona(persona_id=persona_name, frontmatter=fm, body_markdown=body)

    def default_body_if_missing(self, persona_name: str) -> LoadedPersona:
        """Minimalna persona gdy brak pliku (dev / test)."""
        fm = PersonaFrontmatter.model_validate(
            {
                "name": persona_name,
                "display_name": persona_name,
                "tts_emotion_bias": "neutral",
            }
        )
        return LoadedPersona(
            persona_id=persona_name,
            frontmatter=fm,
            body_markdown="## Osobowość\n\nDomyślna persona (placeholder).",
        )


__all__ = ["LoadedPersona", "PersonaFrontmatter", "PersonaLoader"]
