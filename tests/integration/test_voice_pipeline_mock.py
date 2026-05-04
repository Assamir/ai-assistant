"""Integracja mock: audio → STT → LLM → TTS."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.services.voice_pipeline import voice_reply_from_audio


@pytest.mark.asyncio
async def test_voice_reply_pipeline_calls_chain():
    stt = AsyncMock()
    stt.transcribe = AsyncMock(return_value="co tam")

    llm = AsyncMock()
    llm.generate_response = AsyncMock(return_value="Nic.")

    tts = AsyncMock()
    fake_wav = b"RIFF....WAVE"
    tts.speak = AsyncMock(return_value=fake_wav)

    ut, rt, wav = await voice_reply_from_audio(
        b"\x00\x01\x02",
        stt=stt,
        llm=llm,
        tts=tts,
        reply_emotion="neutral",
    )

    assert ut == "co tam"
    assert rt == "Nic."
    assert wav == fake_wav

    stt.transcribe.assert_awaited_once_with(b"\x00\x01\x02")
    llm.generate_response.assert_awaited_once_with("co tam")
    tts.speak.assert_awaited_once_with("Nic.", emotion="neutral")
