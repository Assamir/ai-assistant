"""Adapter STT — Faster-Whisper (CTranslate2) z kolejką GPU i progami pewności."""

from __future__ import annotations

import asyncio
import io
import math
import wave
from enum import Enum
from typing import Any, Callable, List, Optional, Tuple

import numpy as np

from backend.config.schema import STTConfig
from backend.core.interfaces import BaseSTTEngine, GPUScheduler


class ConfidenceTier(str, Enum):
    HIGH = "high"
    LOW = "low"
    REJECT = "reject"


class TranscriptionRejected(RuntimeError):
    """Transkrypcja odrzucona — pewność poniżej `confidence_floor`."""

    def __init__(self, confidence: float, tier: ConfidenceTier = ConfidenceTier.REJECT):
        super().__init__(f"Transcription rejected (confidence={confidence:.3f})")
        self.confidence = confidence
        self.tier = tier


def normalize_audio_to_float32_mono(
    audio_data: bytes,
    *,
    assumed_sample_rate_hz: int,
) -> Tuple[np.ndarray, int]:
    """
    WAV PCM → float32 mono [-1, 1]; brak nagłówka WAV → założenie raw s16le mono @ assumed_sample_rate_hz.
    """
    if len(audio_data) == 0:
        return np.zeros(0, dtype=np.float32), assumed_sample_rate_hz

    if len(audio_data) >= 12 and audio_data[:4] == b"RIFF" and audio_data[8:12] == b"WAVE":
        with wave.open(io.BytesIO(audio_data), "rb") as wf:
            sr = wf.getframerate()
            nch = wf.getnchannels()
            sw = wf.getsampwidth()
            frames = wf.readframes(wf.getnframes())
        if sw != 2:
            raise ValueError(f"Unsupported WAV sample width: {sw} (expected 16-bit)")
        pcm = np.frombuffer(frames, dtype=np.int16)
        if nch > 1:
            pcm = pcm.reshape(-1, nch).mean(axis=1).astype(np.int16)
        fl = pcm.astype(np.float32) / 32768.0
        return np.clip(fl, -1.0, 1.0), sr

    pcm = np.frombuffer(audio_data, dtype=np.int16)
    fl = pcm.astype(np.float32) / 32768.0
    return np.clip(fl, -1.0, 1.0), assumed_sample_rate_hz


def confidence_from_segments_and_info(
    segments: List[Any],
    info: Any,
) -> float:
    """Heurystyka pewności z segmentów Whisper i TranscriptionInfo."""
    logps: List[float] = []
    for seg in segments:
        lp = getattr(seg, "avg_logprob", None)
        if lp is not None:
            logps.append(float(lp))
    if logps:
        mean_lp = sum(logps) / len(logps)
        return float(min(1.0, max(0.0, math.exp(mean_lp))))

    lang_p = getattr(info, "language_probability", None)
    if lang_p is not None:
        return float(min(1.0, max(0.0, float(lang_p))))

    return 0.55


class FasterWhisperSTT(BaseSTTEngine):
    """faster-whisper z opcjonalnym GPUScheduler (priorytet STT = 1)."""

    STT_GPU_PRIORITY = 1

    def __init__(
        self,
        stt_config: STTConfig,
        *,
        gpu_scheduler: Optional[GPUScheduler] = None,
        model: Any = None,
        device: str = "auto",
        compute_type: str = "int8",
        input_sample_rate_hz: int = 16000,
        model_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._cfg = stt_config
        self._scheduler = gpu_scheduler
        self._model = model
        self._device = device
        self._compute_type = compute_type
        self._input_sr = input_sample_rate_hz
        self._model_factory = model_factory
        self._lock = asyncio.Lock()
        self._cached_blob: Optional[bytes] = None
        self._cached_text: str = ""
        self._cached_conf: float = 0.0

    def _ensure_model_loaded(self) -> Any:
        if self._model is not None:
            return self._model
        if self._model_factory is not None:
            self._model = self._model_factory()
            return self._model
        from faster_whisper import WhisperModel

        dev = self._device
        if dev == "auto":
            try:
                import torch

                dev = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                dev = "cpu"
        self._model = WhisperModel(
            self._cfg.model_name,
            device=dev,
            compute_type=self._compute_type,
        )
        return self._model

    def _tier(self, confidence: float) -> ConfidenceTier:
        if confidence >= self._cfg.confidence_threshold:
            return ConfidenceTier.HIGH
        if confidence >= self._cfg.confidence_floor:
            return ConfidenceTier.LOW
        return ConfidenceTier.REJECT

    def transcribe_with_details(self) -> Tuple[str, float, ConfidenceTier]:
        """Ostatni wynik po `transcribe` / `get_confidence` (cache)."""
        return self._cached_text, self._cached_conf, self._tier(self._cached_conf)

    def _transcribe_sync(self, audio_data: bytes) -> Tuple[str, float]:
        samples, _sr = normalize_audio_to_float32_mono(
            audio_data,
            assumed_sample_rate_hz=self._input_sr,
        )
        if samples.size == 0:
            return "", 0.0

        model = self._ensure_model_loaded()
        segments_iter, info = model.transcribe(
            samples,
            language=self._cfg.language if self._cfg.language else None,
            beam_size=self._cfg.beam_size,
            vad_filter=False,
        )
        segments = list(segments_iter)
        text = "".join(getattr(s, "text", "") for s in segments).strip()
        conf = confidence_from_segments_and_info(segments, info)
        return text, conf

    async def _ensure_cached(self, audio_data: bytes) -> None:
        async with self._lock:
            if audio_data == self._cached_blob:
                return

            async def job():
                return await asyncio.to_thread(self._transcribe_sync, audio_data)

            if self._scheduler is not None:
                text, conf = await self._scheduler.submit(job(), priority=self.STT_GPU_PRIORITY)
            else:
                text, conf = await job()

            self._cached_blob = audio_data
            self._cached_text = text
            self._cached_conf = conf

    async def transcribe(self, audio_data: bytes) -> str:
        await self._ensure_cached(audio_data)
        tier = self._tier(self._cached_conf)
        if tier == ConfidenceTier.REJECT:
            raise TranscriptionRejected(self._cached_conf, tier)
        return self._cached_text

    async def get_confidence(self, audio_data: bytes) -> float:
        await self._ensure_cached(audio_data)
        return self._cached_conf


__all__ = [
    "FasterWhisperSTT",
    "ConfidenceTier",
    "TranscriptionRejected",
    "normalize_audio_to_float32_mono",
    "confidence_from_segments_and_info",
]
