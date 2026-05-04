"""Ścieżki zgodne z ENV_SETUP / content root."""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def resolve_config_yaml(content_root: Path) -> Optional[Path]:
    """Szuka config.yaml pod content_root (ENV_SETUP: …/config/config.yaml)."""
    candidates = (
        content_root / "config" / "config.yaml",
        content_root / "config.yaml",
    )
    for p in candidates:
        if p.is_file():
            return p.resolve()
    return None


def sqlite_database_path(content_root: Path) -> Path:
    """Plik SQLite: `{content_root}/data/assystent.db`."""
    data = (content_root / "data").resolve()
    return data / "assystent.db"


__all__ = ["resolve_config_yaml", "sqlite_database_path"]
