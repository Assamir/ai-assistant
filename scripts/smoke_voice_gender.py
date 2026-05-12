"""Sprawdza realnie czy model używa formy żeńskiej po zmianie voice_gender."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.ai.llama_cpp_client import LlamaCppLocalClient
from backend.config.loader import ConfigLoader
from backend.core.prompt_builder import PromptBuilder, detect_voice_gender
from backend.services.llm_model_manager import LLMModelManager


async def main() -> int:
    cfg = ConfigLoader().load_config("config/config.yaml")
    root = Path(cfg.general.content_root).expanduser().resolve()
    mgr = LLMModelManager(
        cache_dir=root / "models" / "llm",
        custom_yaml_path=root / "data" / "llm_models_custom.yaml",
    )
    existing = mgr.is_downloaded(cfg.llm.local.model_id, file=cfg.llm.local.model_file)
    if existing is None:
        print("Model nie pobrany — uruchom najpierw smoke_llm_local.py")
        return 2

    client = LlamaCppLocalClient(cfg.llm, model_path=existing.local_path)
    pb = PromptBuilder(max_context_tokens=4096)
    voice_gender = detect_voice_gender(cfg.tts.piper_voice_onnx_path)
    print(f"piper_voice = {cfg.tts.piper_voice_onnx_path}")
    print(f"detected gender = {voice_gender}")

    user_q = "Powiedz krotko o sobie - jak sie czujesz dzisiaj i co ostatnio robilas/robiles?"
    for gender in ("female", "male"):
        msgs = pb.build_messages(
            assistant_name="Aria",
            content_root=".",
            persona_body_markdown="## Osobowość\n\nJestem Aria — pomocna, ciepla, konkretna.",
            history_messages=[],
            output_mode="text",
            voice_gender=gender,
            include_agentic_section=False,
            include_threads_section=False,
        )
        msgs.append({"role": "user", "content": user_q})
        res = await client.chat_completion(msgs, max_tokens=120)
        print()
        print(f"=== voice_gender={gender} ===")
        print(res.content.strip())
    await client.aclose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
