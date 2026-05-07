"""Testy PiperTTS — mock subprocess / _invoke_piper_cli."""

from __future__ import annotations

import pytest

from backend.ai.piper_tts import PiperTTS, _minimal_silent_wav
from backend.config.schema import TTSConfig


@pytest.fixture
def piper_cfg() -> TTSConfig:
    return TTSConfig(
        piper_voice_onnx_path="C:/models/pl_PL-test.onnx",
        piper_executable="piper",
        chunk_bytes=512,
        voice_speed=1.0,
        emotion_modulation=True,
    )


@pytest.mark.asyncio
async def test_empty_text_returns_minimal_wav(piper_cfg: TTSConfig):
    tts = PiperTTS(piper_cfg)
    out = await tts.speak("   ")
    assert out.startswith(b"RIFF")
    assert len(out) > 40


@pytest.mark.asyncio
async def test_non_empty_requires_onnx_path():
    cfg = TTSConfig(piper_voice_onnx_path=None)
    tts = PiperTTS(cfg)
    with pytest.raises(ValueError, match="piper_voice_onnx_path"):
        await tts.speak("hello")


@pytest.mark.asyncio
async def test_happy_emotion_uses_shorter_length_scale_than_neutral(piper_cfg: TTSConfig):
    scales: list[float] = []

    async def capture(_text: str, ls: float) -> bytes:
        scales.append(ls)
        return _minimal_silent_wav()

    tts = PiperTTS(piper_cfg)
    tts._invoke_piper_cli = capture  # type: ignore[method-assign]

    await tts.speak("test", emotion="neutral")
    await tts.speak("test", emotion="happy")
    assert scales[1] < scales[0]


@pytest.mark.asyncio
async def test_emotion_modulation_off_ignores_emotion_speed(piper_cfg: TTSConfig):
    piper_cfg.emotion_modulation = False
    scales: list[float] = []

    async def capture(_text: str, ls: float) -> bytes:
        scales.append(ls)
        return _minimal_silent_wav()

    tts = PiperTTS(piper_cfg)
    tts._invoke_piper_cli = capture  # type: ignore[method-assign]

    await tts.speak("x", emotion="happy")
    await tts.speak("x", emotion="neutral")
    assert scales[0] == scales[1]


@pytest.mark.asyncio
async def test_stream_to_tts_yields_chunks(piper_cfg: TTSConfig):
    tts = PiperTTS(piper_cfg)

    async def fake_invoke(_text: str, _ls: float) -> bytes:
        return b"\xaa\xbb" * 300

    tts._invoke_piper_cli = fake_invoke  # type: ignore[method-assign]

    chunks = []
    async for part in tts.stream_to_tts("hello"):
        chunks.append(part)
    assert len(chunks) >= 2
    assert sum(len(c) for c in chunks) == 600


@pytest.mark.asyncio
async def test_subprocess_failure_raises(piper_cfg: TTSConfig):
    def bad_sync(text: str, length_scale: float, exe: str, onnx: str) -> bytes:
        raise RuntimeError("Piper failed (exit 1): broken")

    tts = PiperTTS(piper_cfg, sync_runner=bad_sync)

    with pytest.raises(RuntimeError, match="Piper failed"):
        await tts._invoke_piper_cli("txt", 1.0)
