"""Koordynacja wejścia głosowego (PTT vs wakeword), duck oraz backendowy hotkey PTT (pynput). T2."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional

import numpy as np

_logger = logging.getLogger(__name__)


class AudioInputMode(str, Enum):
    PTT = "ptt"
    WAKEWORD = "wakeword"


@dataclass(frozen=True)
class AudioDuckSignal:
    target_volume: float
    ramp_ms: int


class AudioBackendUnavailable(RuntimeError):
    """Brak pynput lub nieobsługiwany klawisz PTT."""


@dataclass
class VoiceInputCoordinator:
    """Emituje sygnały duck przy PTT (frontend / WebSocket mapuje je na zdarzenie `audio_duck`)."""

    mode: AudioInputMode = AudioInputMode.PTT
    duck_sink: Optional[Callable[[AudioDuckSignal], None]] = None
    signals: List[AudioDuckSignal] = field(default_factory=list)
    ptt_held: bool = False

    def __post_init__(self) -> None:
        if self.duck_sink is None:
            self.duck_sink = lambda _sig: None

    def _emit(self, sig: AudioDuckSignal) -> None:
        self.signals.append(sig)
        self.duck_sink(sig)

    def on_ptt_press(self) -> None:
        self.ptt_held = True
        self._emit(AudioDuckSignal(target_volume=0.0, ramp_ms=80))

    def on_ptt_release(self) -> AudioDuckSignal:
        self.ptt_held = False
        sig = AudioDuckSignal(target_volume=1.0, ramp_ms=120)
        self._emit(sig)
        return sig

    def set_frontend_ptt(self, active: bool) -> None:
        """Synchronizacja z `ptt_start` / `ptt_end` z WebSocket (bez ponownego duck)."""
        self.ptt_held = bool(active)


def resolve_ptt_key_name(name: str):
    """Mapuje `ptt_key_name` z konfiguracji na obiekt klawisza pynput (`Key` lub pojedynczy znak)."""
    try:
        from pynput.keyboard import Key
    except ImportError as e:
        raise AudioBackendUnavailable("pynput nie jest zainstalowany") from e

    normalized = name.lower().strip().replace(" ", "_").replace("-", "_")
    aliases = {
        "caps_lock": Key.caps_lock,
        "capslock": Key.caps_lock,
        "scroll_lock": Key.scroll_lock,
        "scrolllock": Key.scroll_lock,
        "space": Key.space,
    }
    if normalized in aliases:
        return aliases[normalized]
    if hasattr(Key, normalized):
        return getattr(Key, normalized)
    if len(normalized) == 1:
        return normalized
    raise ValueError(
        f"Nieznany klawisz PTT „{name}”: podaj np. caps_lock, f13 lub pojedynczy znak."
    )


class PTTHotkeyListener:
    """Globalny nasłuch PTT (pynput) w osobnym wątku — wywołuje VoiceInputCoordinator."""

    __slots__ = ("_coord", "_key_target", "_listener")

    def __init__(
        self,
        coordinator: VoiceInputCoordinator,
        *,
        key_name: str = "caps_lock",
    ) -> None:
        self._coord = coordinator
        self._key_target = key_name
        self._listener: Optional[object] = None

    def start(self) -> None:
        from pynput import keyboard

        target = resolve_ptt_key_name(self._key_target)

        def _matches(event_key: object) -> bool:
            if isinstance(target, str):
                try:
                    ck = getattr(event_key, "char", None)
                except AttributeError:
                    ck = None
                return ck == target
            return event_key == target

        def on_press(key: object) -> None:
            if _matches(key):
                self._coord.on_ptt_press()

        def on_release(key: object) -> None:
            if _matches(key):
                self._coord.on_ptt_release()

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.start()

    def stop(self) -> None:
        if self._listener is None:
            return
        try:
            self._listener.stop()
        finally:
            self._listener = None


class WakewordDetector:
    """Detektor openWakeWord (CPU); fallback model „hey_jarvis”. Bez pakietu / błąd load → brak inferencji."""

    __slots__ = (
        "_config_enabled",
        "_models",
        "threshold",
        "_model",
        "_load_error",
    )

    def __init__(
        self,
        *,
        enabled: bool = False,
        wakeword_models: Optional[list[str]] = None,
        threshold: float = 0.5,
    ) -> None:
        self._config_enabled = enabled
        self._models = list(wakeword_models or ["hey_jarvis"])
        self.threshold = threshold
        self._model: object | None = None
        self._load_error: Optional[str] = None

    @property
    def enabled(self) -> bool:
        """Zamiar z konfiguracji — wakeword ma być używany."""
        return self._config_enabled

    @property
    def ready(self) -> bool:
        """Model załadowany i gotowy do inferencji."""
        return self._model is not None

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    def _ensure_model(self) -> None:
        if self._model is not None or not self._config_enabled:
            return
        try:
            import openwakeword as oww
            from openwakeword.model import Model

            try:
                oww.utils.download_models()
            except Exception:
                _logger.debug("openWakeWord download_models — pominięto lub częściowy sukces", exc_info=True)

            self._model = Model(wakeword_models=self._models)
            self._load_error = None
        except ImportError as e:
            self._load_error = f"openwakeword nie jest zainstalowany: {e}"
            _logger.warning("Wakeword wyłączony — %s", self._load_error)
        except Exception as exc:
            self._load_error = str(exc)
            _logger.warning("Wakeword — nie udało się załadować modelu: %s", exc)

    @staticmethod
    def _scores_triggered(scores: object, threshold: float) -> bool:
        if not isinstance(scores, dict):
            return False
        for v in scores.values():
            if isinstance(v, np.ndarray):
                try:
                    if float(np.max(v)) >= threshold:
                        return True
                except Exception:
                    continue
                continue
            try:
                fv = float(v)  # obejmuje numpy scalar / Decimal itp.
            except (TypeError, ValueError):
                continue
            if fv >= threshold:
                return True
        return False

    async def detect_in_chunk(self, pcm_int16_mono_16khz: np.ndarray) -> bool:
        """
        Jedna ramka PCM int16 mono @ 16 kHz (np. wielokrotność 1280 próbek = 80 ms).
        Zwraca True, gdy którykolwiek model ≥ threshold.
        """
        if not self._config_enabled:
            return False
        self._ensure_model()
        if self._model is None:
            return False
        model = self._model

        def _infer() -> object:
            predict = getattr(model, "predict")
            return predict(pcm_int16_mono_16khz)

        scores = await asyncio.to_thread(_infer)
        return self._scores_triggered(scores, self.threshold)

    async def poll_once(self) -> bool:
        """Kompatybilność wsteczna — bez strumienia audio nie ma pojedynczej próbki do oceny."""
        return False


__all__ = [
    "AudioBackendUnavailable",
    "AudioDuckSignal",
    "AudioInputMode",
    "PTTHotkeyListener",
    "VoiceInputCoordinator",
    "WakewordDetector",
    "resolve_ptt_key_name",
]
