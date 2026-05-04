"""Budżety czasu dla pipeline głosowego (dev / CI baseline, bez prawdziwej gry)."""

from __future__ import annotations

import time

import pytest

from unittest.mock import AsyncMock

from backend.services.voice_pipeline import voice_reply_from_audio


@pytest.mark.asyncio
async def test_voice_pipeline_mock_under_latency_budget():
    """Łańcuch mock STT→LLM→TTS powinien zmieścić się w rozsądnym czasie (T4 smoke)."""
    stt = AsyncMock()
    stt.transcribe = AsyncMock(return_value="hej")
    llm = AsyncMock()
    llm.generate_response = AsyncMock(return_value="Siema.")
    tts = AsyncMock()
    tts.speak = AsyncMock(return_value=b"RIFF....WAVE")

    t0 = time.perf_counter()
    await voice_reply_from_audio(
        b"\x00\x01",
        stt=stt,
        llm=llm,
        tts=tts,
        reply_emotion="neutral",
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert elapsed_ms < 3000.0, f"mock pipeline took {elapsed_ms:.0f}ms (budget 3000ms PTt→reply proxy)"
