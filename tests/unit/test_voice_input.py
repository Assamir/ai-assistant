"""VoiceInputCoordinator, WakewordDetector, PTT hotkey resolution."""

from __future__ import annotations

import pytest
import numpy as np

from backend.ai.voice_input import (
    AudioDuckSignal,
    AudioInputMode,
    PTTHotkeyListener,
    VoiceInputCoordinator,
    WakewordDetector,
    resolve_ptt_key_name,
)


def test_ptt_emits_duck_press_then_release():
    seq: list[AudioDuckSignal] = []

    coord = VoiceInputCoordinator(
        mode=AudioInputMode.PTT,
        duck_sink=lambda s: seq.append(s),
    )
    coord.on_ptt_press()
    coord.on_ptt_release()

    assert len(seq) == 2
    assert seq[0].target_volume == 0.0 and seq[0].ramp_ms == 80
    assert seq[1].target_volume == 1.0 and seq[1].ramp_ms == 120


def test_coordinator_default_sink_no_crash():
    c = VoiceInputCoordinator()
    c.on_ptt_press()
    c.on_ptt_release()
    assert len(c.signals) == 2


@pytest.mark.asyncio
async def test_wakeword_stub_poll_once():
    w = WakewordDetector(enabled=False)
    assert not w.enabled
    assert await w.poll_once() is False


@pytest.mark.asyncio
async def test_wakeword_disabled_never_detects_even_with_model():
    class _M:
        def predict(self, x, **kwargs):
            return {"hey_jarvis": 1.0}

    w = WakewordDetector(enabled=False)
    w._model = _M()
    chunk = np.zeros(1280, dtype=np.int16)
    assert await w.detect_in_chunk(chunk) is False


@pytest.mark.asyncio
async def test_wakeword_detect_positive_with_injected_model():
    class _M:
        def predict(self, x, **kwargs):
            return {"hey_jarvis": 0.95}

    w = WakewordDetector(enabled=True, threshold=0.5)
    w._model = _M()
    chunk = np.zeros(1280, dtype=np.int16)
    assert await w.detect_in_chunk(chunk) is True


@pytest.mark.asyncio
async def test_wakeword_detect_negative_low_scores():
    class _M:
        def predict(self, x, **kwargs):
            return {"hey_jarvis": 0.01}

    w = WakewordDetector(enabled=True, threshold=0.5)
    w._model = _M()
    chunk = np.zeros(1280, dtype=np.int16)
    assert await w.detect_in_chunk(chunk) is False


def test_ptt_listener_stop_without_start_safe():
    c = VoiceInputCoordinator()
    lst = PTTHotkeyListener(c)
    lst.stop()


def test_resolve_caps_lock_when_pynput_installed():
    pytest.importorskip("pynput")
    assert resolve_ptt_key_name("caps_lock") == resolve_ptt_key_name("Caps Lock")


def test_resolve_unknown_key_raises_when_pynput_installed():
    pytest.importorskip("pynput")
    with pytest.raises(ValueError, match="Nieznany"):
        resolve_ptt_key_name("__no_such_key__")
