"""
Weryfikacja środowiska — importy Python i jednorazowa migracja SQLite (tydzień 1).
Uruchom z katalogu głównego repo: python scripts/verify_env.py
"""

from __future__ import annotations

import importlib
import sys
import tempfile
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))

    py = sys.version_info
    print(f"Python {py.major}.{py.minor}.{py.micro}")

    if py < (3, 11):
        print("UWAGA: Zalecane Python >= 3.11 (ENV_SETUP.md).")

    modules = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "yaml",
        "aiosqlite",
        "structlog",
        "watchdog",
        "httpx",
        "numpy",
    ]
    for name in modules:
        importlib.import_module(name)
        print(f"  OK import {name}")

    try:
        importlib.import_module("faster_whisper")
        print("  OK import faster_whisper")
    except ImportError as e:
        print(f"  (opcjonalnie) faster_whisper niedostępny: {e}")

    from backend.db.migration_runner import MigrationRunner

    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "verify.db"
        MigrationRunner(str(db_path)).run_migrations()
        st = MigrationRunner(str(db_path)).get_migration_status()
        print(f"  OK migracje SQLite (wersja {st['current_version']})")

    print("verify_env: sukces")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
