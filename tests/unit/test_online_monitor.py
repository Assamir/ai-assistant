"""Testy jednostkowe OnlineMonitor."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.services.online_monitor import OnlineMonitor, _tcp_probe


# ---------------------------------------------------------------------------
# _tcp_probe
# ---------------------------------------------------------------------------

def test_tcp_probe_returns_true_on_success():
    with patch("backend.services.online_monitor.socket.create_connection"):
        assert _tcp_probe() is True


def test_tcp_probe_returns_false_on_os_error():
    with patch(
        "backend.services.online_monitor.socket.create_connection",
        side_effect=OSError("unreachable"),
    ):
        assert _tcp_probe() is False


# ---------------------------------------------------------------------------
# OnlineMonitor._tick
# ---------------------------------------------------------------------------

async def test_tick_sets_online_true_when_probe_succeeds():
    state: dict = {"online": False}
    monitor = OnlineMonitor(state)
    with patch("backend.services.online_monitor._tcp_probe", return_value=True):
        await monitor._tick()
    assert state["online"] is True


async def test_tick_sets_online_false_when_probe_fails():
    state: dict = {"online": True}
    monitor = OnlineMonitor(state)
    with patch("backend.services.online_monitor._tcp_probe", return_value=False):
        await monitor._tick()
    assert state["online"] is False


async def test_tick_broadcasts_on_transition_online_to_offline():
    state: dict = {"online": True}
    events: list[tuple[str, dict]] = []

    async def capture(ev: str, pl: dict) -> None:
        events.append((ev, pl))

    monitor = OnlineMonitor(state, broadcast_fn=capture)
    with patch("backend.services.online_monitor._tcp_probe", return_value=False):
        await monitor._tick()

    assert len(events) == 1
    assert events[0][0] == "system_state"
    assert events[0][1]["state"] == "offline"
    assert events[0][1]["health"] == "degraded"


async def test_tick_broadcasts_on_transition_offline_to_online():
    state: dict = {"online": False}
    events: list[tuple[str, dict]] = []

    async def capture(ev: str, pl: dict) -> None:
        events.append((ev, pl))

    monitor = OnlineMonitor(state, broadcast_fn=capture)
    with patch("backend.services.online_monitor._tcp_probe", return_value=True):
        await monitor._tick()

    assert len(events) == 1
    assert events[0][1]["state"] == "online"
    assert events[0][1]["health"] == "ok"


async def test_tick_no_broadcast_when_state_unchanged():
    state: dict = {"online": True}
    events: list[tuple[str, dict]] = []

    async def capture(ev: str, pl: dict) -> None:
        events.append((ev, pl))

    monitor = OnlineMonitor(state, broadcast_fn=capture)
    with patch("backend.services.online_monitor._tcp_probe", return_value=True):
        await monitor._tick()

    assert events == []


async def test_tick_no_broadcast_when_probe_unchanged_false():
    state: dict = {"online": False}
    events: list[tuple[str, dict]] = []

    async def capture(ev: str, pl: dict) -> None:
        events.append((ev, pl))

    monitor = OnlineMonitor(state, broadcast_fn=capture)
    with patch("backend.services.online_monitor._tcp_probe", return_value=False):
        await monitor._tick()

    assert events == []


# ---------------------------------------------------------------------------
# OnlineMonitor.run_forever / stop
# ---------------------------------------------------------------------------

async def test_run_forever_stops_on_stop():
    import asyncio

    state: dict = {"online": True}
    monitor = OnlineMonitor(state, interval_seconds=60.0)

    with patch("backend.services.online_monitor._tcp_probe", return_value=True):
        task = asyncio.create_task(monitor.run_forever())
        await asyncio.sleep(0)  # let first tick run
        monitor.stop()
        await asyncio.wait_for(task, timeout=1.0)

    assert not task.cancelled()


async def test_run_forever_performs_initial_tick():
    state: dict = {"online": True}
    monitor = OnlineMonitor(state, interval_seconds=999.0)

    with patch("backend.services.online_monitor._tcp_probe", return_value=False):
        import asyncio
        task = asyncio.create_task(monitor.run_forever())
        await asyncio.sleep(0)
        monitor.stop()
        await asyncio.wait_for(task, timeout=1.0)

    assert state["online"] is False
