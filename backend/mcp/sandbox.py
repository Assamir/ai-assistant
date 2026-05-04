"""Walidacja sandbox dla narzędzi MCP (ścieżki, URL, tryb online)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping


class SandboxViolation(Exception):
    """Naruszenie polityki sandbox (ścieżka, URL, itd.)."""


class OfflineModeError(Exception):
    """Operacja wymaga połączenia — system oznaczony jako offline."""


class SandboxValidator:
    """Wspólna walidacja przed wywołaniem narzędzi (DOK-10 §A)."""

    def __init__(self, content_root: str) -> None:
        self._root = Path(content_root).resolve()

    def validate_path(self, path: str) -> Path:
        p = (self._root / path).resolve()
        root_s = str(self._root)
        p_s = str(p)
        if not p_s.startswith(root_s):
            raise SandboxViolation(f"Path outside content root: {path}")
        return p

    def validate_url(self, url: str) -> str:
        u = url.strip()
        if not re.match(r"^https?://", u, re.IGNORECASE):
            raise SandboxViolation(f"Invalid URL scheme: {url!r}")
        return u

    def check_online_mode(self, system_state: Mapping[str, Any]) -> None:
        if not system_state.get("online", True):
            raise OfflineModeError("Brak połączenia z internetem")


__all__ = [
    "OfflineModeError",
    "SandboxValidator",
    "SandboxViolation",
]
