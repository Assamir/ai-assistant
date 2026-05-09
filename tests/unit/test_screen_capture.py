"""T5 — ScreenCapture: parser DXcam, mock async API."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from backend.ai.screen_capture import (
    MINIMAL_PNG_BYTES,
    MockScreenCapture,
    ScreenCaptureError,
    _mss_probe_ok,
    parse_dxcam_output_info,
)
from backend.config.schema import MonitorInfo
from backend.core.interfaces import BaseScreenCapture


SAMPLE_DXCAM_OUTPUT_INFO = (
    "Device[0] Output[0]: Res:(1920, 1080) Rot:0 Primary:True\n"
    "Device[0] Output[1]: Res:(1920, 1080) Rot:0 Primary:False\n"
)


def test_parse_dxcam_output_info_sample():
    mons = parse_dxcam_output_info(SAMPLE_DXCAM_OUTPUT_INFO)
    assert len(mons) == 2
    assert mons[0].index == 0
    assert mons[0].device_idx == 0 and mons[0].output_idx == 0
    assert mons[0].width == 1920 and mons[0].height == 1080
    assert mons[0].is_primary is True
    assert mons[1].index == 1
    assert mons[1].is_primary is False


def test_mss_probe_ok_requires_successful_grab(monkeypatch):
    class FakeShot:
        width = 100
        height = 50

    class FakeSct:
        monitors = [{"top": 0, "left": 0, "width": 1, "height": 1}, {"top": 0, "left": 0, "width": 100, "height": 50}]

        def grab(self, region):
            return FakeShot()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    m = MagicMock()
    m.MSS.return_value = FakeSct()
    monkeypatch.setitem(sys.modules, "mss", m)
    assert _mss_probe_ok() is True


def test_mss_probe_ok_fails_when_only_virtual_monitor(monkeypatch):
    class FakeSct:
        monitors = [{"top": 0, "left": 0, "width": 1, "height": 1}]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    m = MagicMock()
    m.MSS.return_value = FakeSct()
    monkeypatch.setitem(sys.modules, "mss", m)
    assert _mss_probe_ok() is False


@pytest.mark.asyncio
async def test_mock_screen_capture_returns_png_and_monitors():
    cap = MockScreenCapture()
    assert isinstance(cap, BaseScreenCapture)
    mons = await cap.list_monitors()
    assert len(mons) == 1
    assert mons[0].width == 1920
    png = await cap.capture_png(monitor_index=0)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert png == MINIMAL_PNG_BYTES


@pytest.mark.asyncio
async def test_mock_screen_capture_monitor_index_range():
    dual = [
        MonitorInfo(index=0, width=800, height=600, label="a"),
        MonitorInfo(index=1, width=1024, height=768, label="b"),
    ]
    cap = MockScreenCapture(monitors=dual)
    with pytest.raises(ScreenCaptureError):
        await cap.capture_png(monitor_index=2)
    await cap.capture_png(monitor_index=1)


@pytest.mark.asyncio
async def test_mock_screen_capture_custom_payload():
    payload = b"\x89PNG\r\n\x1a\nCUSTOM"
    cap = MockScreenCapture(png_payload=payload)
    assert await cap.capture_png() == payload
