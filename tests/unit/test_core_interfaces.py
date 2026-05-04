"""GPUScheduler i CircuitBreaker — podstawowe testy zgodności z DOK-08."""

from __future__ import annotations

import asyncio

import pytest

from backend.core.interfaces import CircuitBreaker, CircuitBreakerOpen, GPUScheduler


@pytest.mark.asyncio
async def test_gpu_scheduler_priority_order():
    order: list[str] = []
    gate = asyncio.Event()

    async def slow_a():
        await gate.wait()
        order.append("a")
        return "a"

    async def fast_b():
        order.append("b")
        return "b"

    async def fast_c():
        order.append("c")
        return "c"

    sched = GPUScheduler()
    t_a = asyncio.create_task(sched.submit(slow_a(), priority=3))
    await asyncio.sleep(0)
    t_b = asyncio.create_task(sched.submit(fast_b(), priority=1))
    t_c = asyncio.create_task(sched.submit(fast_c(), priority=2))
    gate.set()
    await asyncio.gather(t_a, t_b, t_c)
    assert order == ["a", "b", "c"]


@pytest.mark.filterwarnings("ignore:coroutine .* was never awaited:RuntimeWarning")
@pytest.mark.asyncio
async def test_gpu_scheduler_invalid_priority():
    sched = GPUScheduler()

    async def noop():
        return None

    with pytest.raises(ValueError, match="Invalid priority"):
        await sched.submit(noop(), priority=9)


def test_circuit_breaker_opens_after_failures():
    cb = CircuitBreaker(failure_threshold=2, timeout_seconds=3600)

    def boom():
        raise ValueError("fail")

    cb.call(lambda: None)
    assert cb.state == "CLOSED"

    with pytest.raises(ValueError):
        cb.call(boom)
    assert cb.state == "CLOSED"

    with pytest.raises(ValueError):
        cb.call(boom)
    assert cb.state == "OPEN"

    with pytest.raises(CircuitBreakerOpen):
        cb.call(lambda: None)


def test_circuit_zero_timeout_recovers():
    cb = CircuitBreaker(failure_threshold=1, timeout_seconds=0)
    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert cb.state == "OPEN"
    cb.call(lambda: "ok")
    assert cb.state == "CLOSED"


def test_circuit_half_open_failure_reopens():
    cb = CircuitBreaker(failure_threshold=1, timeout_seconds=0)
    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert cb.state == "OPEN"
    with pytest.raises(RuntimeError):
        cb.call(lambda: (_ for _ in ()).throw(RuntimeError("y")))
    assert cb.state == "OPEN"


@pytest.mark.asyncio
async def test_circuit_breaker_async_success():
    cb = CircuitBreaker(failure_threshold=3, timeout_seconds=60)

    async def ok():
        return 42

    assert await cb.call_async(ok) == 42
    assert cb.state == "CLOSED"
