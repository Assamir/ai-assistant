"""EasyOCREngine — mock readtext."""

from __future__ import annotations

import pytest

from backend.ai.easyocr_engine import EasyOCREngine
from backend.ai.screen_capture import MINIMAL_PNG_BYTES
from backend.config.schema import OCRConfig
from backend.core.interfaces import GPUScheduler


@pytest.fixture
def ocr_cfg() -> OCRConfig:
    return OCRConfig(enabled=True, languages=["en"], use_gpu=False)


@pytest.mark.asyncio
async def test_easyocr_extract_filters_confidence(ocr_cfg: OCRConfig):
    class _Reader:
        def readtext(self, _arr):
            return [
                ([], "keep", 0.9),
                ([], "drop", 0.1),
            ]

    eng = EasyOCREngine(ocr_cfg.model_copy(update={"confidence_threshold": 0.5}), reader=_Reader())
    assert await eng.extract_text(MINIMAL_PNG_BYTES) == "keep"


@pytest.mark.asyncio
async def test_easyocr_empty_image_raises(ocr_cfg: OCRConfig):
    class _R:
        def readtext(self, _arr):
            return []

    eng = EasyOCREngine(ocr_cfg, reader=_R())
    with pytest.raises(ValueError, match="empty"):
        await eng.extract_text(b"")


class _SpyGPUSched(GPUScheduler):
    def __init__(self) -> None:
        super().__init__()
        self.prios: list[int] = []

    async def submit(self, coro, priority: int = 3):  # type: ignore[override]
        self.prios.append(int(priority))
        return await super().submit(coro, priority)


@pytest.mark.asyncio
async def test_easyocr_uses_scheduler_priority(ocr_cfg: OCRConfig):
    class _Reader:
        def readtext(self, _arr):
            return [([], "x", 1.0)]

    sched = _SpyGPUSched()
    eng = EasyOCREngine(ocr_cfg, gpu_scheduler=sched, reader=_Reader())
    await eng.extract_text(MINIMAL_PNG_BYTES)
    assert sched.prios == [ocr_cfg.gpu_priority]
