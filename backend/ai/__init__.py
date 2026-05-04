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
from backend.ai.moondream_vlm import Moondream2VLM, MoondreamDependencyError
from backend.ai.piper_tts import PiperTTS
from backend.ai.voice_input import (
    AudioBackendUnavailable,
    AudioDuckSignal,
    AudioInputMode,
    PTTHotkeyListener,
    VoiceInputCoordinator,
    WakewordDetector,
    resolve_ptt_key_name,
)
from backend.ai.screen_capture import (
    DesktopScreenCapture,
    MINIMAL_PNG_BYTES,
    MockScreenCapture,
    ScreenCaptureError,
    ScreenCaptureUnavailable,
    parse_dxcam_output_info,
)

__all__ = [
    "LMStudioClient",
    "ChatCompletionResult",
    "Moondream2VLM",
    "MoondreamDependencyError",
    "FasterWhisperSTT",
    "ConfidenceTier",
    "TranscriptionRejected",
    "PiperTTS",
    "AudioInputMode",
    "AudioBackendUnavailable",
    "AudioDuckSignal",
    "VoiceInputCoordinator",
    "WakewordDetector",
    "PTTHotkeyListener",
    "resolve_ptt_key_name",
    "DesktopScreenCapture",
    "MINIMAL_PNG_BYTES",
    "MockScreenCapture",
    "ScreenCaptureError",
    "ScreenCaptureUnavailable",
    "parse_dxcam_output_info",
]
