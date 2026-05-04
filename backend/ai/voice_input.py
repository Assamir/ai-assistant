"""Koordynacja wejścia głosowego (PTT vs wakeword) i sygnałów audio duck (tydzień 2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional


class AudioInputMode(str, Enum):
    PTT = "ptt"
    WAKEWORD = "wakeword"


@dataclass(frozen=True)
class AudioDuckSignal:
    target_volume: float
    ramp_ms: int


@dataclass
class VoiceInputCoordinator:
    """Emituje sygnały duck przy PTT (frontend / WebSocket mapuje je na zdarzenie `audio_duck`)."""

    mode: AudioInputMode = AudioInputMode.PTT
    duck_sink: Optional[Callable[[AudioDuckSignal], None]] = None
    signals: List[AudioDuckSignal] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.duck_sink is None:
            self.duck_sink = lambda _sig: None

    def _emit(self, sig: AudioDuckSignal) -> None:
        self.signals.append(sig)
        self.duck_sink(sig)

    def on_ptt_press(self) -> None:
        self._emit(AudioDuckSignal(target_volume=0.0, ramp_ms=80))

    def on_ptt_release(self) -> AudioDuckSignal:
        sig = AudioDuckSignal(target_volume=1.0, ramp_ms=120)
        self._emit(sig)
        return sig


class WakewordDetector:
    """Placeholder pod openWakeWord — domyślnie wyłączony (integracja w kolejnej iteracji)."""

    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def poll_once(self) -> bool:
        """True gdy wykryto wakeword — stub zwraca zawsze False."""
        return False


__all__ = [
    "AudioInputMode",
    "AudioDuckSignal",
    "VoiceInputCoordinator",
    "WakewordDetector",
]
