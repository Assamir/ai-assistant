"""Orkiestracja łańcucha głosowego: audio → STT → LLM → TTS (tydzień 2, integracja mock)."""

from __future__ import annotations

from typing import Optional, Tuple

from backend.core.interfaces import BaseLLMClient, BaseSTTEngine, BaseTTSEngine


async def voice_reply_from_audio(
    audio_pcm: bytes,
    *,
    stt: BaseSTTEngine,
    llm: BaseLLMClient,
    tts: BaseTTSEngine,
    reply_emotion: Optional[str] = None,
) -> Tuple[str, str, bytes]:
    """
    Zwraca (tekst_użytkownika, odpowiedź_asystenta, audio_wav_bytes).
    """
    user_text = await stt.transcribe(audio_pcm)
    reply_text = await llm.generate_response(user_text)
    wav = await tts.speak(reply_text, emotion=reply_emotion)
    return user_text, reply_text, wav


__all__ = ["voice_reply_from_audio"]
