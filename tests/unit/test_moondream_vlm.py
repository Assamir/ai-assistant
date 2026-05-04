"""Moondream2 VLM adapter — mock model i priorytet GPUScheduler."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.ai.moondream_vlm import Moondream2VLM
from backend.ai.screen_capture import MINIMAL_PNG_BYTES
from backend.config.schema import VLMConfig
from backend.core.interfaces import GPUScheduler


@pytest.fixture
def vlm_cfg() -> VLMConfig:
    return VLMConfig(enabled=True, revision=None)


@pytest.mark.asyncio
async def test_moondream_analyze_caption_mock(vlm_cfg: VLMConfig):
    class _FakeModel:
        def caption(self, image, length="normal", stream=False, **_kw):  # noqa: ARG002
            assert stream is False
            return {"caption": "mock HUD"}

        def query(self, *args, **kwargs):  # noqa: ARG002
            raise AssertionError("query should not run without prompt")

    vlm = Moondream2VLM(vlm_cfg, model=_FakeModel())
    out = await vlm.analyze_image(MINIMAL_PNG_BYTES)
    assert out == "mock HUD"


@pytest.mark.asyncio
async def test_moondream_analyze_query_mock(vlm_cfg: VLMConfig):
    class _FakeModel:
        def caption(self, *args, **kwargs):  # noqa: ARG002
            raise AssertionError("caption should not run when analysis_prompt set")

        def query(self, image, q):  # noqa: ARG002
            return {"answer": f"a:{q}"}

    cfg = vlm_cfg.model_copy(update={"analysis_prompt": "What is visible?"})
    vlm = Moondream2VLM(cfg, model=_FakeModel())
    assert await vlm.analyze_image(MINIMAL_PNG_BYTES) == "a:What is visible?"


def test_moondream_legacy_model_name_normalized():
    cfg = VLMConfig(enabled=True, model_name="moondream2", revision=None)
    assert cfg.model_name == "vikhyatk/moondream2"


@pytest.mark.asyncio
async def test_moondream_empty_payload_raises():
    cfg = VLMConfig(enabled=True, revision=None)
    fake = MagicMock()
    vlm = Moondream2VLM(cfg, model=fake)
    with pytest.raises(ValueError, match="empty"):
        await vlm.analyze_image(b"")


class _SpyScheduler(GPUScheduler):
    def __init__(self) -> None:
        super().__init__()
        self.priorities: list[int] = []

    async def submit(self, coro, priority: int = 3):  # type: ignore[override]
        self.priorities.append(int(priority))
        return await super().submit(coro, priority)


@pytest.mark.asyncio
async def test_moondream_submits_with_config_gpu_priority(vlm_cfg: VLMConfig):
    class _FakeModel:
        def caption(self, image, length="normal", stream=False, **_kw):  # noqa: ARG002
            return {"caption": "ok"}

    sched = _SpyScheduler()
    vlm = Moondream2VLM(vlm_cfg, gpu_scheduler=sched, model=_FakeModel())
    assert await vlm.analyze_image(MINIMAL_PNG_BYTES) == "ok"
    assert sched.priorities == [vlm_cfg.gpu_priority]
