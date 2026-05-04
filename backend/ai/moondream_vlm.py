"""Moondream2 jako BaseVLMAnalyzer — lazy transformers + GPUScheduler P4 (T5 dzień 2)."""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Any, Callable, Optional

from PIL import Image

from backend.config.schema import VLMConfig
from backend.core.interfaces import BaseVLMAnalyzer, GPUScheduler

_logger = logging.getLogger(__name__)


class MoondreamDependencyError(RuntimeError):
    """Wymagane są opcjonalne zależności vision (torch, transformers)."""


def _flatten_caption_payload(payload: object) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload.strip()
    if hasattr(payload, "__iter__") and not isinstance(payload, (bytes, dict, str)):
        try:
            return "".join(str(x) for x in payload).strip()
        except Exception:
            return str(payload).strip()
    return str(payload).strip()


class Moondream2VLM(BaseVLMAnalyzer):
    """HF `vikhyatk/moondream2` (trust_remote_code) — caption lub visual query."""

    def __init__(
        self,
        vlm_config: VLMConfig,
        *,
        gpu_scheduler: Optional[GPUScheduler] = None,
        model: Any = None,
        model_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._cfg = vlm_config
        self._scheduler = gpu_scheduler
        self._model = model
        self._model_factory = model_factory
        self._lock = asyncio.Lock()
        self._gpu_prio = int(vlm_config.gpu_priority)

    def _ensure_model_loaded(self) -> Any:
        if self._model is not None:
            return self._model
        if self._model_factory is not None:
            self._model = self._model_factory()
            return self._model

        try:
            import torch
            from transformers import AutoModelForCausalLM
        except ImportError as e:
            raise MoondreamDependencyError(
                "Zainstaluj torch oraz transformers (np. pip install torch transformers accelerate)."
            ) from e

        device_kind = self._resolve_device(torch)
        dtype = self._resolve_dtype(torch, device_kind)

        load_kw: dict[str, Any] = {
            "trust_remote_code": True,
            "torch_dtype": dtype,
            "device_map": {"": device_kind},
        }
        if self._cfg.revision:
            load_kw["revision"] = self._cfg.revision

        _logger.info("Loading Moondream model %s (device=%s)", self._cfg.model_name, device_kind)
        self._model = AutoModelForCausalLM.from_pretrained(self._cfg.model_name, **load_kw)
        return self._model

    def _resolve_device(self, torch_module: Any) -> str:
        d = self._cfg.device
        if d == "cuda":
            if not torch_module.cuda.is_available():
                _logger.warning("VLM device=cuda niedostępny — używam CPU.")
                return "cpu"
            return "cuda"
        if d == "mps":
            has_mps = bool(getattr(torch_module.backends, "mps", None) and torch_module.backends.mps.is_available())
            if not has_mps:
                _logger.warning("VLM device=mps niedostępny — używam CPU.")
                return "cpu"
            return "mps"
        if d == "cpu":
            return "cpu"
        if torch_module.cuda.is_available():
            return "cuda"
        if getattr(torch_module.backends, "mps", None) and torch_module.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _resolve_dtype(self, torch_module: Any, device_kind: str) -> Any:
        cfg = self._cfg.dtype
        if cfg == "float16":
            return torch_module.float16
        if cfg == "float32":
            return torch_module.float32
        if cfg == "bfloat16":
            return torch_module.bfloat16
        if device_kind == "cpu":
            return torch_module.float32
        return torch_module.float16

    def _analyze_sync(self, image_data: bytes) -> str:
        if not image_data:
            raise ValueError("image_data is empty")

        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        model = self._ensure_model_loaded()

        prompt = (self._cfg.analysis_prompt or "").strip()
        if prompt:
            result = model.query(image, prompt)
            return _flatten_caption_payload(result.get("answer") if isinstance(result, dict) else result)

        result = model.caption(image, length=self._cfg.caption_length, stream=False)
        if not isinstance(result, dict):
            return _flatten_caption_payload(result)

        cap = result.get("caption")
        return _flatten_caption_payload(cap)

    async def analyze_image(self, image_data: bytes) -> str:
        async with self._lock:

            async def job() -> str:
                return await asyncio.to_thread(self._analyze_sync, image_data)

            if self._scheduler is not None:
                return await self._scheduler.submit(job(), priority=self._gpu_prio)
            return await job()


__all__ = ["Moondream2VLM", "MoondreamDependencyError"]
