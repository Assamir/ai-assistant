"""EasyOCR jako BaseOCREngine — wątek + opcjonalny GPUScheduler (T5 dzień 3)."""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Any, Callable, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from backend.config.schema import OCRConfig
from backend.core.interfaces import BaseOCREngine, GPUScheduler

_logger = logging.getLogger(__name__)


class OCRDependencyError(RuntimeError):
    """Brak pakietu easyocr (pip install easyocr)."""


EasyOCRLine = Tuple[Any, str, float]


class EasyOCREngine(BaseOCREngine):
    """Lazy `easyocr.Reader`; `readtext` w asyncio.to_thread."""

    def __init__(
        self,
        ocr_config: OCRConfig,
        *,
        gpu_scheduler: Optional[GPUScheduler] = None,
        reader: Any = None,
        reader_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._cfg = ocr_config
        self._scheduler = gpu_scheduler
        self._reader = reader
        self._reader_factory = reader_factory
        self._lock = asyncio.Lock()
        self._gpu_prio = int(ocr_config.gpu_priority)

    def _cuda_available(self) -> bool:
        if not self._cfg.use_gpu:
            return False
        try:
            import torch

            return bool(torch.cuda.is_available())
        except Exception:
            return False

    def _ensure_reader(self) -> Any:
        if self._reader is not None:
            return self._reader
        if self._reader_factory is not None:
            self._reader = self._reader_factory()
            return self._reader
        try:
            import easyocr
        except ImportError as e:
            raise OCRDependencyError("Zainstaluj easyocr (pip install easyocr).") from e

        gpu = self._cuda_available()
        _logger.info("EasyOCR Reader init languages=%s gpu=%s", self._cfg.languages, gpu)
        self._reader = easyocr.Reader(self._cfg.languages, gpu=gpu)
        return self._reader

    def _extract_sync(self, image_data: bytes) -> str:
        if not image_data:
            raise ValueError("image_data is empty")

        img = Image.open(io.BytesIO(image_data)).convert("RGB")
        arr = np.asarray(img, dtype=np.uint8)
        reader = self._ensure_reader()
        raw: Sequence[EasyOCRLine] = reader.readtext(arr)
        lines: List[str] = []
        thr = float(self._cfg.confidence_threshold)
        for row in raw:
            if len(row) < 3:
                continue
            text, conf = row[1], float(row[2])
            if conf >= thr:
                t = (text or "").strip()
                if t:
                    lines.append(t)
        return "\n".join(lines).strip()

    async def extract_text(self, image_data: bytes) -> str:
        async with self._lock:

            async def job() -> str:
                return await asyncio.to_thread(self._extract_sync, image_data)

            if self._scheduler is not None:
                return await self._scheduler.submit(job(), priority=self._gpu_prio)
            return await job()


__all__ = ["EasyOCREngine", "OCRDependencyError"]
