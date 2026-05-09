"""Generates a short sine-wave notification ping WAV (stdlib only, no deps)."""

from __future__ import annotations

import io
import math
import wave


def generate_ping_wav(
    freq: float = 880.0,
    duration_ms: int = 120,
    sample_rate: int = 22050,
    amplitude: float = 0.22,
) -> bytes:
    """Return a mono 16-bit WAV with a single sine tone at *freq* Hz.

    The envelope is a linear fade-out to avoid a click at the end.
    Default: 880 Hz (A5), 120 ms — subtle but audible over game audio.
    """
    n = int(sample_rate * duration_ms / 1000)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n):
            env = 1.0 - (i / n)
            val = amplitude * env * math.sin(2.0 * math.pi * freq * i / sample_rate)
            iv = max(-32767, min(32767, int(val * 32767)))
            frames += iv.to_bytes(2, byteorder="little", signed=True)
        wf.writeframes(bytes(frames))
    return buf.getvalue()


def generate_silence_wav(*, duration_ms: int = 80, sample_rate: int = 22050) -> bytes:
    """Krótki ciszy WAV (mono 16-bit) — REST/TTS podczas ciszy nocnej bez kosztu Piper."""
    n = max(1, int(sample_rate * duration_ms / 1000))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n)
    return buf.getvalue()
