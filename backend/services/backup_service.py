"""Serwis backup — ZIP content_root do {content_root}/backups/."""

from __future__ import annotations

import asyncio
import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

_logger = logging.getLogger(__name__)

# Katalogi (względem content_root) wyłączone z backupu
_EXCLUDE_DIRS: frozenset[str] = frozenset({"backups", "chroma"})
# Sufiks pliku → pomiń (transient SQLite / temporalne)
_EXCLUDE_SUFFIXES: frozenset[str] = frozenset({".db-wal", ".db-shm", ".tmp"})
# Ile backupów trzymać (starsze usuwamy)
MAX_BACKUP_FILES: int = 10

BroadcastFn = Callable[[str, Dict[str, Any]], Awaitable[None]]


def backup_filename() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H.%M")
    return f"backup_{ts}.zip"


def _should_include(path: Path, content_root: Path) -> bool:
    try:
        rel = path.relative_to(content_root)
    except ValueError:
        return False
    if rel.parts and rel.parts[0] in _EXCLUDE_DIRS:
        return False
    if path.suffix in _EXCLUDE_SUFFIXES:
        return False
    return True


def _create_zip(content_root: Path, dest: Path) -> int:
    """Tworzy ZIP synchronicznie. Zwraca rozmiar pliku w bajtach."""
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file in sorted(content_root.rglob("*")):
            if file.is_file() and _should_include(file, content_root):
                zf.write(file, file.relative_to(content_root))
    return dest.stat().st_size


def _rotate_old_backups(backup_dir: Path, keep: int = MAX_BACKUP_FILES) -> None:
    zips = sorted(backup_dir.glob("backup_*.zip"), key=lambda p: p.stat().st_mtime)
    for old in zips[:-keep] if len(zips) > keep else []:
        try:
            old.unlink()
            _logger.debug("Usunięto stary backup: %s", old.name)
        except OSError as exc:
            _logger.warning("Nie można usunąć starego backupu %s: %s", old.name, exc)


async def run_backup(
    content_root: Path,
    *,
    broadcast_fn: Optional[BroadcastFn] = None,
) -> Dict[str, Any]:
    """Tworzy ZIP content_root asynchronicznie (blokująca część w executor).

    Wyklucza: backups/, data/chroma/, pliki *.db-wal / *.db-shm / *.tmp.
    Po sukcesie rotuje stare backupy (zachowuje MAX_BACKUP_FILES).
    Jeśli broadcast_fn podane — emituje ``backup_done`` lub ``backup_error``.
    """
    backup_dir = content_root / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    filename = backup_filename()
    dest = backup_dir / filename

    try:
        loop = asyncio.get_running_loop()
        size_bytes: int = await loop.run_in_executor(None, _create_zip, content_root, dest)
        _rotate_old_backups(backup_dir)
        rel_path = f"backups/{filename}"
        result: Dict[str, Any] = {
            "ok": True,
            "path": rel_path,
            "filename": filename,
            "size_bytes": size_bytes,
        }
        _logger.info("Backup utworzony: %s (%d B)", dest, size_bytes)
        if broadcast_fn:
            await broadcast_fn("backup_done", result)
        return result
    except Exception as exc:
        _logger.error("Backup nie powiódł się: %s", exc, exc_info=True)
        if dest.exists():
            try:
                dest.unlink()
            except OSError:
                pass
        error: Dict[str, Any] = {"ok": False, "error": str(exc)}
        if broadcast_fn:
            await broadcast_fn("backup_error", error)
        return error
