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

    try:
        importlib.import_module("librosa")
        importlib.import_module("soundfile")
        print("  OK import librosa + soundfile")
    except ImportError as e:
        print(f"  (opcjonalnie) librosa/soundfile niedostępny: {e}")

    try:
        importlib.import_module("tiktoken")
        importlib.import_module("asteval")
        print("  OK import tiktoken + asteval")
    except ImportError as e:
        print(f"  (opcjonalnie) tiktoken/asteval niedostępny: {e}")

    try:
        import setuptools

        print(
            f"  setuptools {setuptools.__version__} "
            "(torch often requires setuptools<82; pip downgrade is OK)"
        )
    except ImportError:
        print("  (missing setuptools — unusual)")

    try:
        import torch

        tv = getattr(torch, "__version__", "?")
        print(f"  OK import torch ({tv})")
        cuda_ok = bool(torch.cuda.is_available())
        print(f"  torch.cuda.is_available() = {cuda_ok}")
        if cuda_ok:
            print(f"  CUDA device 0: {torch.cuda.get_device_name(0)}")
        elif "+cpu" in tv.lower():
            print("  Info: CPU torch wheel (+cpu); for NVIDIA GPU see ENV_SETUP.md section 4.4 / pytorch.org")
    except ImportError as e:
        print(f"  (optional) torch — VLM/Moondream: pip install torch transformers accelerate — {e}")

    try:
        import transformers

        print(f"  OK import transformers ({transformers.__version__})")
    except ImportError as e:
        print(f"  (opcjonalnie) transformers — {e}")

    try:
        import accelerate

        print(f"  OK import accelerate ({accelerate.__version__})")
    except ImportError:
        print("  (opcjonalnie) accelerate — zalecane przy transformers / device_map")

    try:
        importlib.import_module("PIL")
        print("  OK import Pillow (PIL)")
    except ImportError as e:
        print(f"  (opcjonalnie) Pillow — {e}")

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
