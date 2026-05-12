"""Menedżer modeli LLM dla providera `local`: katalog + pobieranie z HuggingFace.

- `INITIAL_MODELS` + customowe wpisy z `data/llm_models_custom.yaml` tworzą katalog.
- `ensure_downloaded` pobiera GGUF z HF i zwraca lokalną ścieżkę (idempotentne — HF
  Hub cache sprawdza ETag i nie pobiera ponownie).
- Postęp pobierania emitowany jako WS event `model_download_progress`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, List, Optional

from backend.ai.llm_models_catalog import (
    INITIAL_MODELS,
    ModelEntry,
    load_custom_models,
    merge_catalog,
    parse_model_id,
    save_custom_models,
)

_logger = logging.getLogger(__name__)


@dataclass
class DownloadedModel:
    model_id: str
    local_path: str
    size_bytes: int
    quant: Optional[str]


# Sygnatura asynchronicznego progress callback:
ProgressCb = Callable[[str, int, int, str], Awaitable[None]]
# (model_id, downloaded_bytes, total_bytes, status)


def _normalize_repo_dir_name(repo_id: str) -> str:
    """Zamienia '/' na '_' i wycina znaki niedozwolone w nazwach katalogów."""
    return repo_id.replace("/", "_").replace("\\", "_")


def _pick_gguf_by_quant(files: List[str], preferred_quant: str) -> Optional[str]:
    """Wybiera plik .gguf — najpierw pasujący do preferred_quant, potem najmniejszy."""
    ggufs = [f for f in files if f.lower().endswith(".gguf")]
    if not ggufs:
        return None
    needle = preferred_quant.lower()
    for f in ggufs:
        if needle in f.lower():
            return f
    return sorted(ggufs)[0]


def _detect_quant(filename: str) -> Optional[str]:
    """Wyciąga oznaczenie kwantyzacji z nazwy pliku (np. 'Q4_K_M', 'Q8_0')."""
    import re
    m = re.search(r"(Q\d[_A-Z0-9]*)", filename, re.IGNORECASE)
    return m.group(1).upper() if m else None


class LLMModelManager:
    """Wybór modelu, pobieranie z HF i katalog custom-wpisów."""

    def __init__(
        self,
        cache_dir: Path,
        custom_yaml_path: Path,
        progress_callback: Optional[ProgressCb] = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.custom_yaml_path = Path(custom_yaml_path)
        self._progress_cb = progress_callback

    # ---------- Katalog ----------

    def list_catalog(self) -> List[ModelEntry]:
        return merge_catalog(self.custom_yaml_path)

    def list_initial(self) -> List[ModelEntry]:
        return list(INITIAL_MODELS)

    def list_custom(self) -> List[ModelEntry]:
        return load_custom_models(self.custom_yaml_path)

    def add_custom_model(self, entry: ModelEntry) -> None:
        entry.is_custom = True
        current = self.list_custom()
        current = [e for e in current if e.model_id != entry.model_id]
        current.append(entry)
        save_custom_models(self.custom_yaml_path, current)

    def remove_custom_model(self, model_id: str) -> bool:
        current = self.list_custom()
        new = [e for e in current if e.model_id != model_id]
        if len(new) == len(current):
            return False
        save_custom_models(self.custom_yaml_path, new)
        return True

    # ---------- Cache na dysku ----------

    def _model_cache_dir(self, repo_id: str) -> Path:
        return self.cache_dir / _normalize_repo_dir_name(repo_id)

    def list_downloaded(self) -> List[DownloadedModel]:
        """Skanuje cache_dir w poszukiwaniu pobranych plików GGUF."""
        out: List[DownloadedModel] = []
        if not self.cache_dir.exists():
            return out
        for sub in self.cache_dir.iterdir():
            if not sub.is_dir():
                continue
            # repo_id rekonstruowany z nazwy folderu: pierwszy '_' = separator owner/repo
            name = sub.name
            if "_" not in name:
                continue
            owner, _, repo = name.partition("_")
            repo_id = f"{owner}/{repo}"
            for gguf in sub.rglob("*.gguf"):
                try:
                    size = gguf.stat().st_size
                except OSError:
                    continue
                out.append(DownloadedModel(
                    model_id=repo_id,
                    local_path=str(gguf.resolve()),
                    size_bytes=size,
                    quant=_detect_quant(gguf.name),
                ))
        return out

    def is_downloaded(self, model_id: str, *, file: Optional[str] = None) -> Optional[DownloadedModel]:
        """Zwraca DownloadedModel jeśli model jest w cache (po model_id [+ pliku])."""
        repo_id, parsed_file = parse_model_id(model_id)
        target_file = file or parsed_file
        target_dir = self._model_cache_dir(repo_id)
        if not target_dir.exists():
            return None
        if target_file:
            candidate = target_dir / target_file
            if candidate.exists():
                return DownloadedModel(
                    model_id=repo_id,
                    local_path=str(candidate.resolve()),
                    size_bytes=candidate.stat().st_size,
                    quant=_detect_quant(candidate.name),
                )
            return None
        # Bez konkretnego pliku — bierzemy pierwszy .gguf
        for gguf in sorted(target_dir.rglob("*.gguf")):
            return DownloadedModel(
                model_id=repo_id,
                local_path=str(gguf.resolve()),
                size_bytes=gguf.stat().st_size,
                quant=_detect_quant(gguf.name),
            )
        return None

    def remove_downloaded(self, model_id: str) -> bool:
        repo_id, _ = parse_model_id(model_id)
        target = self._model_cache_dir(repo_id)
        if not target.exists():
            return False
        shutil.rmtree(target, ignore_errors=True)
        return True

    # ---------- Pobieranie ----------

    def _emit_progress_sync(
        self,
        loop: Optional[asyncio.AbstractEventLoop],
        model_id: str,
        downloaded: int,
        total: int,
        status: str,
    ) -> None:
        """Wysyła progress event z wątku roboczego do pętli asyncio (jeśli dostępna)."""
        if self._progress_cb is None or loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self._progress_cb(model_id, downloaded, total, status),
                loop,
            )
        except Exception:
            _logger.debug("Progress callback dispatch failed", exc_info=True)

    def ensure_downloaded_sync(
        self,
        model_id: str,
        *,
        file: Optional[str] = None,
        preferred_quant: str = "Q4_K_M",
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> DownloadedModel:
        """Synchroniczna ścieżka (do wywołania z executora). Idempotentna."""
        from huggingface_hub import hf_hub_download, list_repo_files

        repo_id, parsed_file = parse_model_id(model_id)
        target_file = file or parsed_file
        target_dir = self._model_cache_dir(repo_id)
        target_dir.mkdir(parents=True, exist_ok=True)

        if target_file is None:
            try:
                files = list_repo_files(repo_id)
            except Exception as exc:
                raise RuntimeError(f"Nie mogę pobrać listy plików z {repo_id}: {exc}") from exc
            picked = _pick_gguf_by_quant(files, preferred_quant)
            if picked is None:
                raise RuntimeError(f"Brak plików .gguf w repo {repo_id}")
            target_file = picked

        existing = self.is_downloaded(repo_id, file=target_file)
        if existing is not None:
            self._emit_progress_sync(loop, repo_id, existing.size_bytes, existing.size_bytes, "complete")
            return existing

        self._emit_progress_sync(loop, repo_id, 0, 0, "downloading")
        try:
            local_path = hf_hub_download(
                repo_id=repo_id,
                filename=target_file,
                local_dir=str(target_dir),
                # hf_hub_download używa ETag-based cache; ponowne wywołanie zwraca tę samą ścieżkę bez pobierania
            )
        except Exception as exc:
            self._emit_progress_sync(loop, repo_id, 0, 0, "error")
            raise RuntimeError(f"Pobieranie {repo_id}/{target_file} nie powiodło się: {exc}") from exc

        path = Path(local_path)
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        self._emit_progress_sync(loop, repo_id, size, size, "complete")
        return DownloadedModel(
            model_id=repo_id,
            local_path=str(path.resolve()),
            size_bytes=size,
            quant=_detect_quant(path.name),
        )

    async def ensure_downloaded(
        self,
        model_id: str,
        *,
        file: Optional[str] = None,
        preferred_quant: str = "Q4_K_M",
    ) -> DownloadedModel:
        """Asynchroniczne owinięcie — odpala blokujący download w executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.ensure_downloaded_sync(
                model_id,
                file=file,
                preferred_quant=preferred_quant,
                loop=loop,
            ),
        )


__all__ = [
    "DownloadedModel",
    "LLMModelManager",
    "ProgressCb",
]
