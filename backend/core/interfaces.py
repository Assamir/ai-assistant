from __future__ import annotations

import asyncio
import itertools
import time
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients"""

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Generate a response from the LLM"""
        raise NotImplementedError

    @abstractmethod
    async def stream_response(
        self,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[str]:
        """Stream responses from the LLM token by token"""
        raise NotImplementedError


class BaseSTTEngine(ABC):
    """Abstract base class for Speech-to-Text engines"""

    @abstractmethod
    async def transcribe(self, audio_data: bytes) -> str:
        """Transcribe audio data to text"""
        raise NotImplementedError

    @abstractmethod
    async def get_confidence(self, audio_data: bytes) -> float:
        """Get confidence score for transcription"""
        raise NotImplementedError


class BaseTTSEngine(ABC):
    """Abstract base class for Text-to-Speech engines"""

    @abstractmethod
    async def speak(self, text: str, emotion: Optional[str] = None) -> bytes:
        """Convert text to speech and return audio data"""
        raise NotImplementedError

    @abstractmethod
    async def stream_to_tts(self, text: str) -> AsyncIterator[bytes]:
        """Stream TTS output in chunks"""
        raise NotImplementedError


class BaseVLMAnalyzer(ABC):
    """Abstract base class for Vision-Language Model analyzers"""

    @abstractmethod
    async def analyze_image(self, image_data: bytes) -> str:
        """Analyze an image and return description"""
        raise NotImplementedError


class CircuitBreakerOpen(RuntimeError):
    """Circuit breaker is OPEN — calls are short-circuited."""


class GPUScheduler:
    """Sekwencyjne GPU (mutex) z kolejką priorytetów — niższy numer = wyższy priorytet (1–4)."""

    VALID_PRIORITIES = frozenset({1, 2, 3, 4})

    def __init__(self) -> None:
        self._queue: asyncio.PriorityQueue[
            tuple[int, int, Awaitable[Any], asyncio.Future[Any]]
        ] = asyncio.PriorityQueue()
        self._sem = asyncio.Semaphore(1)
        self._seq = itertools.count()
        self._worker: Optional[asyncio.Task[None]] = None

    def _ensure_worker(self) -> None:
        if self._worker is None or self._worker.done():
            loop = asyncio.get_running_loop()
            self._worker = loop.create_task(self._run_worker())

    async def _run_worker(self) -> None:
        while True:
            _, __, coro, fut = await self._queue.get()
            try:
                async with self._sem:
                    result = await coro
                fut.set_result(result)
            except Exception as e:
                fut.set_exception(e)
            finally:
                self._queue.task_done()

    async def submit(self, coro: Awaitable[Any], priority: int = 3) -> Any:
        if priority not in self.VALID_PRIORITIES:
            raise ValueError(f"Invalid priority {priority}. Must be in {sorted(self.VALID_PRIORITIES)}.")

        self._ensure_worker()
        fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        await self._queue.put((priority, next(self._seq), coro, fut))
        return await fut

    def pending_approx(self) -> int:
        return self._queue.qsize()


class CircuitBreaker:
    """Circuit breaker dla wywołań zewnętrznych (CLOSED / OPEN / HALF_OPEN)."""

    def __init__(self, failure_threshold: int = 5, timeout_seconds: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"

    def call(self, func):
        self._before_call_sync()
        try:
            result = func()
        except Exception:
            self._failure()
            raise
        self._success()
        return result

    async def call_async(self, factory: Callable[[], Awaitable[Any]]) -> Any:
        self._before_call_sync()
        try:
            result = await factory()
        except Exception:
            self._failure()
            raise
        self._success()
        return result

    def check_allow(self) -> None:
        """Zgłaszaj CircuitBreakerOpen, gdy obwód jest OPEN i timeout nie minął."""
        self._before_call_sync()

    def mark_success(self) -> None:
        """Udane wywołanie zewnętrzne (np. po zakończeniu streamu SSE)."""
        self._success()

    def mark_failure(self) -> None:
        """Błąd wywołania zewnętrznego bez owijania w call_async (np. stream)."""
        self._failure()

    def _before_call_sync(self) -> None:
        if self.state == "OPEN":
            if self._timeout_elapsed():
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpen("Circuit breaker is OPEN")

    def _success(self) -> None:
        self.failure_count = 0
        self.state = "CLOSED"

    def _failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.state == "HALF_OPEN":
            self.state = "OPEN"
            return
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

    def _timeout_elapsed(self) -> bool:
        if self.last_failure_time is None:
            return True
        return (time.monotonic() - self.last_failure_time) >= self.timeout_seconds


__all__ = [
    "BaseLLMClient",
    "BaseSTTEngine",
    "BaseTTSEngine",
    "BaseVLMAnalyzer",
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "GPUScheduler",
]
