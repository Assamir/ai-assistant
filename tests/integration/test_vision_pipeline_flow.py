"""T5 — przepływ: mock capture → dHash → DualVisionPipeline (mock VLM)."""

from __future__ import annotations

import pytest

from backend.ai.screen_capture import MockScreenCapture
from backend.ai.scene_dhash import SceneDeduper
from backend.ai.vision_pipeline import DualVisionPipeline, VisionFrameResult
from backend.config.schema import OCRConfig
from backend.core.interfaces import BaseVLMAnalyzer


class _EchoVLM(BaseVLMAnalyzer):
    """Opis zależy od rozmiaru PNG — deterministycznie różny dla różnych klatek."""

    async def analyze_image(self, image_data: bytes) -> str:
        return f"frame_bytes={len(image_data)}"


@pytest.mark.asyncio
async def test_capture_then_vision_pipeline_mock_vlm():
    cap = MockScreenCapture()
    png = await cap.capture_png(monitor_index=0)
    pipe = DualVisionPipeline(
        vlm_engine=_EchoVLM(),
        ocr_engine=None,
        ocr_config=OCRConfig(enabled=False),
    )
    res: VisionFrameResult = await pipe.analyze_png(png)
    assert "frame_bytes=" in res.vlm_text
    assert res.ocr_ran is False
    assert res.ocr_text == ""


@pytest.mark.asyncio
async def test_deduper_skips_second_identical_mock_frame():
    cap = MockScreenCapture()
    png = await cap.capture_png()
    dedup = SceneDeduper(max_similar_distance=2)
    assert dedup.should_skip(png) is False
    assert dedup.should_skip(png) is True
