"""Smoke test providera local: pobierz GGUF + załaduj llama-cpp-python + pojedynczy chat.

Uruchom: .venv\\Scripts\\python.exe scripts/smoke_llm_local.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.ai.llama_cpp_client import LlamaCppLocalClient
from backend.config.loader import ConfigLoader
from backend.services.llm_model_manager import LLMModelManager


async def main() -> int:
    cfg = ConfigLoader().load_config("config/config.yaml")
    print(f"provider={cfg.llm.provider} model_id={cfg.llm.local.model_id} quant={cfg.llm.local.preferred_quant}")
    if cfg.llm.provider != "local":
        print("config.yaml nie ma provider=local — przerywam.")
        return 2

    content_root = Path(cfg.general.content_root).expanduser().resolve()
    cache_dir = (content_root / "models" / "llm").resolve()
    custom = (content_root / "data" / "llm_models_custom.yaml").resolve()
    print(f"cache_dir={cache_dir}")

    mgr = LLMModelManager(cache_dir=cache_dir, custom_yaml_path=custom)

    existing = mgr.is_downloaded(cfg.llm.local.model_id, file=cfg.llm.local.model_file)
    if existing:
        print(f"Juz pobrany: {existing.local_path} ({existing.size_bytes / 1e9:.2f} GB, quant={existing.quant})")
        model_path = existing.local_path
    else:
        print("Pobieranie z HuggingFace (moze zajac kilka minut)...")
        t0 = time.time()
        result = await mgr.ensure_downloaded(
            cfg.llm.local.model_id,
            file=cfg.llm.local.model_file,
            preferred_quant=cfg.llm.local.preferred_quant,
        )
        dt = time.time() - t0
        print(f"Pobrano w {dt:.1f}s -> {result.local_path} ({result.size_bytes / 1e9:.2f} GB)")
        model_path = result.local_path

    print("Tworze LlamaCppLocalClient i laduje model...")
    client = LlamaCppLocalClient(cfg.llm, model_path=model_path)
    t0 = time.time()
    res = await client.chat_completion(
        [
            {"role": "system", "content": "Jestes pomocnym asystentem. Odpowiadaj zwiezle po polsku."},
            {"role": "user", "content": "Powiedz krotko: ile to 2+2 i jaka jest stolica Polski?"},
        ],
        max_tokens=80,
    )
    dt = time.time() - t0
    print(f"Chat OK w {dt:.1f}s")
    print(f"finish_reason: {res.finish_reason}")
    print(f"content: {res.content!r}")
    await client.aclose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
