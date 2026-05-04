"""DualVisionPipeline — logika trigger_keywords i merged_context."""

from __future__ import annotations

import pytest

from backend.ai.screen_capture import MINIMAL_PNG_BYTES
from backend.ai.vision_pipeline import DualVisionPipeline, VisionFrameResult
from backend.config.schema import OCRConfig


class _FakeVLM:
    def __init__(self, text: str) -> None:
        self._text = text

    async def analyze_image(self, image_data: bytes) -> str:
        assert image_data
        return self._text


class _FakeOCR:
    def __init__(self, out: str = "line1") -> None:
        self._out = out
        self.calls = 0

    async def extract_text(self, image_data: bytes) -> str:
        self.calls += 1
        assert image_data
        return self._out


@pytest.mark.asyncio
async def test_pipeline_vlm_only_no_ocr_engine():
    cfg = OCRConfig(enabled=False)
    p = DualVisionPipeline(vlm_engine=_FakeVLM("scene"), ocr_engine=None, ocr_config=cfg)
    r = await p.analyze_png(MINIMAL_PNG_BYTES)
    assert r.vlm_text == "scene"
    assert r.ocr_ran is False


@pytest.mark.asyncio
async def test_pipeline_ocr_always_when_keywords_empty():
    cfg = OCRConfig(enabled=True, trigger_keywords=[])
    ocr = _FakeOCR("loot")
    p = DualVisionPipeline(vlm_engine=_FakeVLM("menu visible"), ocr_engine=ocr, ocr_config=cfg)
    r = await p.analyze_png(MINIMAL_PNG_BYTES)
    assert r.ocr_ran is True and r.ocr_text == "loot"
    assert ocr.calls == 1


@pytest.mark.asyncio
async def test_pipeline_ocr_triggered_by_keyword_match():
    cfg = OCRConfig(enabled=True, trigger_keywords=["inventory"])
    ocr = _FakeOCR()
    p = DualVisionPipeline(vlm_engine=_FakeVLM("The INVENTORY panel is open"), ocr_engine=ocr, ocr_config=cfg)
    r = await p.analyze_png(MINIMAL_PNG_BYTES)
    assert r.ocr_ran is True
    assert ocr.calls == 1


@pytest.mark.asyncio
async def test_pipeline_ocr_skipped_when_keyword_miss():
    cfg = OCRConfig(enabled=True, trigger_keywords=["inventory"])
    ocr = _FakeOCR()
    p = DualVisionPipeline(vlm_engine=_FakeVLM("open field"), ocr_engine=ocr, ocr_config=cfg)
    r = await p.analyze_png(MINIMAL_PNG_BYTES)
    assert r.ocr_ran is False and r.ocr_text == ""
    assert ocr.calls == 0


@pytest.mark.asyncio
async def test_pipeline_ocr_only_without_vlm():
    cfg = OCRConfig(enabled=True, trigger_keywords=["x"])
    ocr = _FakeOCR("solo")
    p = DualVisionPipeline(vlm_engine=None, ocr_engine=ocr, ocr_config=cfg)
    r = await p.analyze_png(MINIMAL_PNG_BYTES)
    assert r.vlm_text == ""
    assert r.ocr_ran is True and r.ocr_text == "solo"


def test_vision_frame_result_merged():
    r = VisionFrameResult(vlm_text="ui", ocr_text="gold 100", ocr_ran=True)
    assert "[OCR]" in r.merged_context()
    assert "gold" in r.merged_context()
