"""Synteza mowy — Piper (CLI) + modulacja emocji (length_scale; opcjonalnie pitch librosa)."""

from __future__ import annotations

import asyncio
import io
import os
import subprocess
import tempfile
import wave
from typing import Any, AsyncIterator, Callable, Optional

from backend.config.schema import TTSConfig
from backend.core.interfaces import BaseTTSEngine

from backend.ai.tts_emotion import combined_speed, emotion_speed_pitch, length_scale_from_speed


def piper_cli_invoker_sync(text: str, length_scale: float, exe: str, onnx: str) -> bytes:
    """Uruchom `piper` przez `subprocess.run` w wątku (kompatybilne z każdą pętlą asyncio na Windows)."""
    fd, out_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        proc = subprocess.run(
            [
                exe,
                "--model",
                onnx,
                "--output_file",
                out_path,
                "--length_scale",
                str(round(length_scale, 6)),
            ],
            input=(text or "").encode("utf-8"),
            capture_output=True,
            timeout=180,
            check=False,
        )
        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
            out = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Piper failed (exit {proc.returncode}): {err or out or 'no stderr'}")
        with open(out_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass


def _minimal_silent_wav(sample_rate: int = 22050, frames: int = 320) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * frames)
    return buf.getvalue()


def _apply_pitch_wav_optional(wav_bytes: bytes, pitch_percent: float) -> bytes:
    if abs(pitch_percent) < 0.05:
        return wav_bytes
    try:
        import librosa  # type: ignore[import-not-found]
        import numpy as np
        import soundfile as sf  # type: ignore[import-not-found]
    except ImportError:
        return wav_bytes

    audio, sr = sf.read(io.BytesIO(wav_bytes))
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    steps = pitch_percent / 100.0 * 12.0
    shifted = librosa.effects.pitch_shift(audio, sr=sr, n_steps=float(steps))
    out = io.BytesIO()
    sf.write(out, shifted, sr, format="WAV", subtype="PCM_16")
    return out.getvalue()


class PiperTTS(BaseTTSEngine):
    """Wywołanie binariów Piper (`piper`) przez subprocess w wątku; unika NotImplementedError na Windows."""

    def __init__(
        self,
        tts_config: TTSConfig,
        *,
        sync_runner: Optional[Callable[[str, float, str, str], bytes]] = None,
    ) -> None:
        self._cfg = tts_config
        self._chunk = max(512, tts_config.chunk_bytes)
        self._sync_runner = sync_runner or piper_cli_invoker_sync

    async def speak(self, text: str, emotion: Optional[str] = None) -> bytes:
        stripped = (text or "").strip()
        if not stripped:
            return _minimal_silent_wav()

        onnx = self._cfg.piper_voice_onnx_path or ""
        if not onnx.strip():
            raise ValueError("TTSConfig.piper_voice_onnx_path is required for PiperTTS")

        cs = combined_speed(self._cfg.voice_speed, emotion if self._cfg.emotion_modulation else None)
        length_scale = length_scale_from_speed(cs)

        wav_core = await self._invoke_piper_cli(stripped, length_scale)
        if self._cfg.emotion_modulation and emotion:
            _, pitch_pct = emotion_speed_pitch(emotion)
            wav_core = _apply_pitch_wav_optional(wav_core, pitch_pct)
        return wav_core

    async def stream_to_tts(self, text: str) -> AsyncIterator[bytes]:
        blob = await self.speak(text, emotion=None)
        for i in range(0, len(blob), self._chunk):
            yield blob[i : i + self._chunk]

    async def _invoke_piper_cli(self, text: str, length_scale: float) -> bytes:
        exe = self._cfg.piper_executable or "piper"
        onnx = self._cfg.piper_voice_onnx_path or ""
        return await asyncio.to_thread(self._sync_runner, text, length_scale, exe, onnx)


__all__ = ["PiperTTS", "_minimal_silent_wav", "piper_cli_invoker_sync"]
