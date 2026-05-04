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
from backend.ai.piper_tts import PiperTTS
from backend.ai.voice_input import (
    AudioDuckSignal,
    AudioInputMode,
    VoiceInputCoordinator,
    WakewordDetector,
)

__all__ = [
    "LMStudioClient",
    "ChatCompletionResult",
    "FasterWhisperSTT",
    "ConfidenceTier",
    "TranscriptionRejected",
    "PiperTTS",
    "AudioInputMode",
    "AudioDuckSignal",
    "VoiceInputCoordinator",
    "WakewordDetector",
]
