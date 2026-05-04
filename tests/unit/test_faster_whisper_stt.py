"""Testy FasterWhisperSTT — mock modelu (bez realnego inference)."""

from __future__ import annotations

import io
import math
import wave
from unittest.mock import MagicMock

import numpy as np
import pytest

from backend.ai.faster_whisper_stt import (
    ConfidenceTier,
    FasterWhisperSTT,
    TranscriptionRejected,
    confidence_from_segments_and_info,
    normalize_audio_to_float32_mono,
)
from backend.config.schema import STTConfig
from backend.core.interfaces import GPUScheduler


class _Seg:
    def __init__(self, text: str, avg_logprob: float):
        self.text = text
        self.avg_logprob = avg_logprob


class _Info:
    def __init__(self, language_probability=None):
        self.language_probability = language_probability


@pytest.fixture
def stt_cfg() -> STTConfig:
    return STTConfig(
        model_name="medium",
        language="pl",
        confidence_threshold=0.8,
        confidence_floor=0.45,
        beam_size=5,
    )


def test_normalize_wav_and_raw_pcm():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes((np.ones(200, dtype=np.int16) * 16000).tobytes())
    wav_bytes = buf.getvalue()
    fl, sr = normalize_audio_to_float32_mono(wav_bytes, assumed_sample_rate_hz=16000)
    assert sr == 16000
    assert fl.dtype == np.float32
    assert fl.shape == (200,)
    assert np.allclose(fl.mean(), 16000 / 32768.0, rtol=0.01)

    raw = np.array([1000, -1000], dtype=np.int16).tobytes()
    fl2, sr2 = normalize_audio_to_float32_mono(raw, assumed_sample_rate_hz=44100)
    assert sr2 == 44100
    assert fl2.shape == (2,)


def test_confidence_from_segments_matches_heuristic():
    conf = confidence_from_segments_and_info([_Seg("", -0.2)], _Info())
    assert conf == pytest.approx(math.exp(-0.2), rel=1e-6)


def _engine(stt_cfg: STTConfig, *, segments_logp: float, scheduler=None):
    seg = _Seg(" dzień dobry", segments_logp)
    info = _Info()
    model = MagicMock()
    model.transcribe.return_value = ([seg], info)
    return FasterWhisperSTT(stt_cfg, gpu_scheduler=scheduler, model=model), model


@pytest.mark.asyncio
async def test_transcribe_high_confidence(stt_cfg: STTConfig):
    stt, model = _engine(stt_cfg, segments_logp=-0.05)
    text = await stt.transcribe(np.zeros(320, dtype=np.int16).tobytes())
    assert "dzień dobry" in text
    model.transcribe.assert_called_once()


@pytest.mark.asyncio
async def test_transcribe_low_confidence_still_returns_text(stt_cfg: STTConfig):
    audio = b"\x01\x00" * 400
    stt, model = _engine(stt_cfg, segments_logp=-0.35)
    text = await stt.transcribe(audio)
    assert text
    assert model.transcribe.call_count == 1
    _, _, tier = stt.transcribe_with_details()
    assert tier == ConfidenceTier.LOW


@pytest.mark.asyncio
async def test_transcribe_reject_below_floor(stt_cfg: STTConfig):
    model = MagicMock()
    model.transcribe.return_value = ([], _Info(language_probability=0.2))
    stt = FasterWhisperSTT(stt_cfg, model=model)
    with pytest.raises(TranscriptionRejected):
        await stt.transcribe(b"\x02\x00" * 200)


@pytest.mark.asyncio
async def test_get_confidence_reuses_single_inference(stt_cfg: STTConfig):
    stt, model = _engine(stt_cfg, segments_logp=-0.1)
    audio = b"\x03\x00" * 128
    await stt.transcribe(audio)
    c = await stt.get_confidence(audio)
    assert c == pytest.approx(math.exp(-0.1), rel=1e-5)
    assert model.transcribe.call_count == 1


@pytest.mark.asyncio
async def test_gpu_scheduler_wraps_inference(stt_cfg: STTConfig):
    sched = GPUScheduler()
    stt, model = _engine(stt_cfg, segments_logp=-0.04, scheduler=sched)
    await stt.transcribe(b"\x04\x00" * 256)
    model.transcribe.assert_called_once()
