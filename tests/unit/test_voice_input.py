"""VoiceInputCoordinator i WakewordDetector (stub)."""

import pytest

from backend.ai.voice_input import (
    AudioDuckSignal,
    AudioInputMode,
    VoiceInputCoordinator,
    WakewordDetector,
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
async def test_wakeword_stub_never_triggers():
    w = WakewordDetector(enabled=False)
    assert not w.enabled
    assert await w.poll_once() is False
