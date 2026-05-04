"""
AI package for Assystent backend.
Contains AI engine implementations (STT, TTS, LLM, VLM).
"""

from backend.ai.faster_whisper_stt import (
    ConfidenceTier,
    FasterWhisperSTT,
    TranscriptionRejected,
)
from backend.ai.llm_client import ChatCompletionResult, LMStudioClient

__all__ = [
    "LMStudioClient",
    "ChatCompletionResult",
    "FasterWhisperSTT",
    "ConfidenceTier",
    "TranscriptionRejected",
]
