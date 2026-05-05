"""Guardrails for desktop release assets (electron-builder)."""

from __future__ import annotations

import json
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_FRONTEND = _REPO_ROOT / "frontend"
_PKG = _FRONTEND / "package.json"


def test_electron_builder_icon_file_exists() -> None:
    icon_rel = json.loads(_PKG.read_text(encoding="utf-8"))["build"]["icon"]
    icon_path = _FRONTEND / icon_rel
    assert icon_path.is_file(), f"missing {icon_path}"


def test_changelog_documents_packaging() -> None:
    changelog = _REPO_ROOT / "CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8")
    assert "Assystent" in text
    assert "electron-builder" in text.lower() or "packaging" in text.lower()
