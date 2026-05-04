"""Obserwacja plików config + personas (watchdog) z debounce i przeładowaniem kontekstu."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import FastAPI
from watchdog.events import FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from backend.api.app_context import AppContext
from backend.config.loader import ConfigLoader
from backend.services.runtime_config import apply_reload_configuration

logger = logging.getLogger(__name__)


class HotReloadHandle:
    def __init__(self, observer: Observer) -> None:
        self._observer = observer

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join(timeout=2.0)


def start_hot_reload(ctx: AppContext, app: FastAPI) -> HotReloadHandle:
    """Uruchamia wątek watchdog; przeładowanie schedulowane na pętlę asyncio serwera."""
    _ = app
    loop = asyncio.get_running_loop()
    root = Path(ctx.config.general.content_root).expanduser()
    personas_dir = root / "personas"

    debounce_seconds: float = 0.45
    pending: Optional[asyncio.TimerHandle] = None

    def schedule(coro_factory: Callable[[], Any]) -> None:
        nonlocal pending
        if pending is not None:
            pending.cancel()

        def fire() -> None:
            nonlocal pending
            pending = None
            asyncio.ensure_future(coro_factory(), loop=loop)

        pending = loop.call_later(debounce_seconds, fire)

    async def reload_yaml() -> None:
        path = ctx.resolved_config_path
        if not path:
            return
        try:
            cfg = ConfigLoader().load_config(path)
        except Exception as exc:
            logger.warning("Hot-reload: failed to parse config: %s", exc)
            return
        await apply_reload_configuration(ctx, cfg)
        await _broadcast_reload(ctx, "config")

    async def notify_persona_touch() -> None:
        await _broadcast_reload(ctx, "personas")

    cfg_resolved: Optional[Path] = None
    if ctx.resolved_config_path:
        cfg_resolved = Path(ctx.resolved_config_path).resolve()

    class Handler(FileSystemEventHandler):
        def on_modified(self, event: object) -> None:
            if not isinstance(event, FileModifiedEvent):
                return
            if event.is_directory:
                return
            try:
                resolved = Path(event.src_path).resolve()
            except OSError:
                return
            if cfg_resolved is not None and resolved == cfg_resolved:
                loop.call_soon_threadsafe(lambda: schedule(reload_yaml))
                return
            try:
                pd = personas_dir.resolve()
                if pd.is_dir() and (resolved == pd or pd in resolved.parents):
                    loop.call_soon_threadsafe(lambda: schedule(notify_persona_touch))
            except (ValueError, OSError):
                pass

        def on_created(self, event: object) -> None:
            self.on_modified(event)

    obs = Observer()
    handler = Handler()
    if ctx.resolved_config_path:
        obs.schedule(handler, str(Path(ctx.resolved_config_path).parent), recursive=False)
    personas_dir.mkdir(parents=True, exist_ok=True)
    obs.schedule(handler, str(personas_dir), recursive=True)

    obs.start()
    logger.info("Config hot-reload watcher started (config + personas)")
    return HotReloadHandle(obs)


async def _broadcast_reload(ctx: AppContext, scope: str) -> None:
    payload = {
        "scope": scope,
        "message_pl": (
            "Konfiguracja przeładowana." if scope == "config" else "Zaktualizowano pliki person."
        ),
    }
    for sid in ctx.websocket_manager.iter_session_ids():
        await ctx.websocket_manager.send_to_session(sid, "config_reloaded", payload)
        await ctx.websocket_manager.send_to_session(
            sid,
            "text_overlay",
            {"text": payload["message_pl"]},
        )


__all__ = ["HotReloadHandle", "start_hot_reload"]
