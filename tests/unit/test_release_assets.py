"""Guardrails for desktop release assets (electron-builder)."""

from __future__ import annotations

from pathlib import Path

import yaml


_REPO_ROOT = Path(__file__).resolve().parents[2]
_FRONTEND = _REPO_ROOT / "frontend"
_BUILDER_CLIENT = _FRONTEND / "electron-builder.client.yml"


def test_electron_builder_icon_file_exists() -> None:
    cfg = yaml.safe_load(_BUILDER_CLIENT.read_text(encoding="utf-8"))
    icon_rel = cfg.get("icon") if isinstance(cfg, dict) else None
    assert isinstance(icon_rel, str) and icon_rel.strip(), "electron-builder.client.yml: brak pola icon"
    icon_path = _FRONTEND / icon_rel
    assert icon_path.is_file(), f"missing {icon_path}"


def test_changelog_documents_packaging() -> None:
    changelog = _REPO_ROOT / "CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8")
    assert "Assystent" in text
    assert "electron-builder" in text.lower() or "packaging" in text.lower()
