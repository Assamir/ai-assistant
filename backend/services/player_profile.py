"""Profil gracza — YAML pod ``data/player_profile.yaml`` (CONFIG_SPEC §6)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.db.repositories import (
    ArchiveReason,
    PlayerContextSnapshotRepository,
    PlayerProfileArchiveRepository,
    SnapshotTrigger,
)

try:
    from yaml import CSafeDumper as _SafeDumper
except ImportError:  # pragma: no cover
    from yaml import SafeDumper as _SafeDumper


class Character(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    char_class: str = Field(alias="class", default="")
    build: str = ""
    level: int = Field(default=1, ge=1, le=100)
    build_url: Optional[str] = None
    notes: str = ""


class GameEntry(BaseModel):
    active_character: Optional[str] = None
    league: str = ""
    game_version: str = ""
    characters: List[Character] = Field(default_factory=list)
    last_meta_check: Optional[date] = None

    @field_validator("last_meta_check", mode="before")
    @classmethod
    def _coerce_last_meta(cls, v: object) -> Optional[date]:
        if v is None or v == "":
            return None
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            try:
                return date.fromisoformat(v.strip()[:10])
            except ValueError:
                return None
        return None

    @model_validator(mode="after")
    def _active_in_characters(self) -> GameEntry:
        if self.active_character:
            names = [c.name for c in self.characters]
            if self.active_character not in names:
                raise ValueError(
                    f"active_character {self.active_character!r} nie występuje w characters ({names})"
                )
        return self


class PlayerProfile(BaseModel):
    games: Dict[str, GameEntry] = Field(default_factory=dict)
    updated_at: str = ""


class PlayerProfileRepository:
    """Źródło prawdy: YAML; snapshoty SQLite przez ``PlayerContextSnapshotRepository``."""

    def __init__(self, yaml_path: str, db_path: str) -> None:
        self._path = Path(yaml_path)
        self._db_path = db_path

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> PlayerProfile:
        if not self._path.is_file():
            return PlayerProfile()
        try:
            raw = yaml.safe_load(self._path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            return PlayerProfile()
        if not isinstance(raw, dict):
            return PlayerProfile()
        try:
            return PlayerProfile.model_validate(raw)
        except Exception:
            return PlayerProfile()

    def save(self, profile: PlayerProfile) -> None:
        profile.updated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = profile.model_dump(mode="json", by_alias=True, exclude_none=False)
        text = yaml.dump(
            data,
            Dumper=_SafeDumper,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
        self._path.write_text(text, encoding="utf-8")

    def summary_for_game(self, game_id: Optional[str]) -> Optional[str]:
        """Krótki tekst do ``PromptBuilder`` (PLAYER_PROFILE_SUMMARY)."""
        if not game_id or not str(game_id).strip():
            return None
        gid = str(game_id).strip()
        p = self.load()
        entry = p.games.get(gid)
        if entry is None:
            return None
        lines: list[str] = [f"Gra: {gid}"]
        if entry.league:
            lines.append(f"Liga / wersja: {entry.league}")
        if entry.game_version:
            lines.append(f"Wersja gry: {entry.game_version}")
        if entry.active_character:
            lines.append(f"Aktywna postać: {entry.active_character}")
            ch = next((c for c in entry.characters if c.name == entry.active_character), None)
            if ch:
                if ch.char_class:
                    lines.append(f"Klasa: {ch.char_class}")
                if ch.build:
                    lines.append(f"Build: {ch.build}")
                if ch.level:
                    lines.append(f"Poziom: {ch.level}")
        if len(lines) <= 1:
            return None
        return "\n".join(lines)

    async def record_snapshot(
        self,
        *,
        session_id: int,
        game_id: str,
        trigger: SnapshotTrigger,
    ) -> Optional[int]:
        """Zapis ``player_context_snapshots`` jeśli profil ma dane dla danej gry."""
        prof = self.load()
        entry = prof.games.get(game_id)
        if entry is None or not entry.active_character:
            return None
        ch = next((c for c in entry.characters if c.name == entry.active_character), None)
        repo = PlayerContextSnapshotRepository(self._db_path)
        return await repo.insert(
            session_id,
            game_id,
            entry.active_character,
            trigger=trigger,
            character_class=ch.char_class if ch else None,
            build_name=ch.build if ch else None,
            build_url=ch.build_url if ch else None,
            league=entry.league or None,
        )

    async def archive_game_entry(
        self,
        *,
        game_id: str,
        season: str,
        reason: ArchiveReason,
    ) -> Optional[int]:
        """Zapisuje snapshot wpisu gry do ``player_profile_archives``. Nie modyfikuje YAML profilu."""
        gid = str(game_id).strip()
        season_clean = str(season).strip()
        if not gid or not season_clean:
            return None
        profile = self.load()
        entry = profile.games.get(gid)
        if entry is None:
            return None
        data = entry.model_dump(mode="json", by_alias=True, exclude_none=False)
        text = yaml.dump(
            data,
            Dumper=_SafeDumper,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
        repo = PlayerProfileArchiveRepository(self._db_path)
        return await repo.insert(gid, season_clean, text, reason)

    async def list_archives(
        self,
        *,
        game: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        repo = PlayerProfileArchiveRepository(self._db_path)
        return await repo.list_recent(game=game, limit=limit)


__all__ = [
    "Character",
    "GameEntry",
    "PlayerProfile",
    "PlayerProfileRepository",
    "ArchiveReason",
]
