"""Katalog modeli LLM dla providera `local` (llama-cpp-python embedded).

Inicjalna lista jest hardkodowana (`INITIAL_MODELS`). Użytkownik dodaje własne
przez REST `POST /api/v1/llm/models` — zapisywane do
`{content_root}/data/llm_models_custom.yaml`.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

_logger = logging.getLogger(__name__)


@dataclass
class ModelEntry:
    """Wpis w katalogu modeli — repo HF + metadane prezentacyjne."""

    model_id: str
    display_name: str
    default_quant: str = "Q4_K_M"
    recommended_n_ctx: int = 8192
    description: str = ""
    license: str = ""
    is_custom: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Modele inicjalne — pokazywane w UI od pierwszego uruchomienia.
# Uwaga: `google/gemma-3-E4B-it` (oryginał Google) jest w safetensors. Dla embedded
# llama-cpp-python wymagany jest GGUF, więc mapujemy go na `unsloth/gemma-3n-E4B-it-GGUF`.
INITIAL_MODELS: List[ModelEntry] = [
    ModelEntry(
        model_id="unsloth/gemma-3n-E4B-it-GGUF",
        display_name="Google Gemma 3n E4B Instruct (GGUF)",
        default_quant="Q4_K_M",
        recommended_n_ctx=8192,
        description=(
            "Wydajny model 4B parametrów efektywnych od Google. GGUF od Unsloth. "
            "Szybki, dobry do dialogu PL, niski VRAM (~3 GB)."
        ),
        license="Gemma Terms of Use",
    ),
    ModelEntry(
        model_id="unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF",
        display_name="Qwen3 Coder 30B (A3B aktywne, GGUF)",
        default_quant="Q4_K_M",
        recommended_n_ctx=16384,
        description=(
            "MoE 30B / ~3B aktywnych parametrów. Mocne function calling i kod. "
            "Wymaga ~18 GB VRAM dla Q4_K_M."
        ),
        license="Apache 2.0",
    ),
]


def parse_model_id(model_id: str) -> tuple[str, Optional[str]]:
    """Rozdziela `owner/repo` (zwraca (repo_id, None)) lub `owner/repo/file.gguf` (repo_id, file)."""
    parts = model_id.strip().strip("/").split("/")
    if len(parts) == 2:
        return f"{parts[0]}/{parts[1]}", None
    if len(parts) >= 3:
        repo_id = f"{parts[0]}/{parts[1]}"
        filename = "/".join(parts[2:])
        return repo_id, filename
    raise ValueError(
        f"Nieprawidłowy format model_id: '{model_id}' "
        f"(oczekiwany 'owner/repo' lub 'owner/repo/filename.gguf')."
    )


def load_custom_models(path: Path) -> List[ModelEntry]:
    """Ładuje custom wpisy z YAML; pusta lista gdy plik nie istnieje lub jest niepoprawny."""
    if not path.exists():
        return []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        _logger.warning("Nie można odczytać %s: %s", path, exc)
        return []
    items = raw.get("models") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        return []
    out: List[ModelEntry] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            out.append(ModelEntry(
                model_id=str(item["model_id"]),
                display_name=str(item.get("display_name", item["model_id"])),
                default_quant=str(item.get("default_quant", "Q4_K_M")),
                recommended_n_ctx=int(item.get("recommended_n_ctx", 8192)),
                description=str(item.get("description", "")),
                license=str(item.get("license", "")),
                is_custom=True,
            ))
        except (KeyError, ValueError) as exc:
            _logger.warning("Pomijam niepoprawny wpis w %s: %s (%s)", path, item, exc)
    return out


def save_custom_models(path: Path, entries: List[ModelEntry]) -> None:
    """Zapisuje custom wpisy do YAML (tylko `is_custom=True`)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    custom = [e.to_dict() for e in entries if e.is_custom]
    payload = {"models": custom}
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def merge_catalog(custom_path: Path) -> List[ModelEntry]:
    """Zwraca INITIAL_MODELS + custom (deduplikacja po model_id, custom nadpisuje)."""
    custom = load_custom_models(custom_path)
    by_id: Dict[str, ModelEntry] = {m.model_id: m for m in INITIAL_MODELS}
    for entry in custom:
        by_id[entry.model_id] = entry
    return list(by_id.values())


__all__ = [
    "ModelEntry",
    "INITIAL_MODELS",
    "parse_model_id",
    "load_custom_models",
    "save_custom_models",
    "merge_catalog",
]
