"""Profile gier — Pydantic + YAML (T6 / OBSERVER_SPEC §3)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator

from backend.services.game_observer import KNOWN_GAMES

_logger = logging.getLogger(__name__)


class ScreenRegion(BaseModel):
    name: str = ""
    position: str = ""
    size_percent: int = Field(default=15, ge=1, le=100)


class GameProfile(BaseModel):
    """Profil pojedynczej gry — plik `content_root/game_profiles/{id}.yaml` lub `config.game_profiles`."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    process_names: List[str] = Field(default_factory=list)
    observer_type: str = "strategy"
    observer_interval_seconds: Optional[int] = Field(default=None, ge=5, le=300)
    focus_areas: List[str] = Field(default_factory=list)
    screen_regions: List[ScreenRegion] = Field(default_factory=list)
    context_prompt: str = ""
    vlm_prompt_template: str = ""

    @field_validator("id", mode="before")
    @classmethod
    def strip_id(cls, v: Any) -> str:
        return str(v).strip()

    @field_validator("process_names", mode="before")
    @classmethod
    def norm_procs(cls, v: Any) -> List[str]:
        if not v:
            return []
        if isinstance(v, str):
            return [v.strip()] if v.strip() else []
        return [str(x).strip() for x in v if str(x).strip()]


def _slug_from_exe(exe: str) -> str:
    stem = exe.lower().replace(".exe", "").strip()
    return stem.replace(" ", "_").replace(".", "_")


def profiles_from_known_games() -> Dict[str, GameProfile]:
    """Minimalne profile ze słownika `KNOWN_GAMES` (proces → nazwa wyświetlana)."""
    out: Dict[str, GameProfile] = {}
    for exe, title in KNOWN_GAMES.items():
        pid = _slug_from_exe(exe)
        out[pid] = GameProfile(
            id=pid,
            name=title,
            process_names=[exe],
            observer_type="strategy",
            focus_areas=[],
            context_prompt="",
        )
    return out


def _load_yaml_file(path: Path) -> Optional[GameProfile]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        _logger.warning("game profile %s: %s", path, exc)
        return None
    if not isinstance(raw, dict):
        return None
    data = dict(raw)
    data.setdefault("id", path.stem)
    try:
        return GameProfile.model_validate(data)
    except Exception as exc:
        _logger.warning("game profile validate %s: %s", path, exc)
        return None


def load_profiles_from_directory(directory: Path) -> Dict[str, GameProfile]:
    if not directory.is_dir():
        return {}
    out: Dict[str, GameProfile] = {}
    seen: set[Path] = set()
    for pattern in ("*.yaml", "*.yml"):
        for path in sorted(directory.glob(pattern)):
            if path in seen:
                continue
            seen.add(path)
            prof = _load_yaml_file(path)
            if prof is not None:
                out[prof.id] = prof
    return out


def merge_inline_config_profiles(raw: Dict[str, Any]) -> Dict[str, GameProfile]:
    out: Dict[str, GameProfile] = {}
    for key, val in raw.items():
        pid = str(key).strip()
        if not pid or not isinstance(val, dict):
            continue
        payload = dict(val)
        payload.setdefault("id", pid)
        payload.setdefault("name", pid)
        try:
            out[pid] = GameProfile.model_validate(payload)
        except Exception as exc:
            _logger.warning("inline game_profiles[%s]: %s", pid, exc)
    return out


def build_game_profile_index(content_root: Path, cfg: Any) -> Dict[str, GameProfile]:
    """
    Kolejność nadpisywania: KNOWN_GAMES → `game_profiles/*.yaml` → `config.game_profiles`.
    """
    merged = profiles_from_known_games()
    dir_prof = load_profiles_from_directory(content_root / "game_profiles")
    merged.update(dir_prof)
    inline = merge_inline_config_profiles(getattr(cfg, "game_profiles", None) or {})
    merged.update(inline)
    return merged


__all__ = [
    "GameProfile",
    "ScreenRegion",
    "build_game_profile_index",
    "load_profiles_from_directory",
    "profiles_from_known_games",
]
