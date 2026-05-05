"""
Main entry point for the Assystent backend service.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from backend.api.app_context import create_app_context, make_game_emitter
from backend.api.routes import router as api_router
from backend.api.ws_router import websocket_endpoint
from backend.db.repositories import SystemStateRepository
from backend.services.config_hot_reload import start_hot_reload
from backend.services.session_watchdog import SessionWatchdog
from backend.ai.voice_input import (
    AudioDuckSignal,
    AudioInputMode,
    PTTHotkeyListener,
    VoiceInputCoordinator,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ctx = create_app_context()
    app.state.ctx = ctx

    loop = asyncio.get_running_loop()

    async def broadcast_duck(sig: AudioDuckSignal) -> None:
        payload = {"target_volume": sig.target_volume, "ramp_ms": sig.ramp_ms}
        for sid in ctx.websocket_manager.iter_session_ids():
            await ctx.websocket_manager.send_to_session(sid, "audio_duck", payload)

    def duck_sink(sig: AudioDuckSignal) -> None:
        fut = asyncio.run_coroutine_threadsafe(broadcast_duck(sig), loop)

        def _done(_f: asyncio.Future[None]) -> None:
            try:
                _f.result()
            except Exception as exc_duck:  # pragma: no cover
                logger.warning("audio_duck broadcast failed: %s", exc_duck)

        fut.add_done_callback(_done)

    ctx.voice_input_coordinator = VoiceInputCoordinator(
        mode=AudioInputMode(ctx.config.audio.input_mode),
        duck_sink=duck_sink,
    )

    ptt_listener: PTTHotkeyListener | None = None
    if ctx.config.audio.backend_ptt_listener_enabled:
        try:
            ptt_listener = PTTHotkeyListener(
                ctx.voice_input_coordinator,
                key_name=ctx.config.audio.ptt_key_name,
            )
            ptt_listener.start()
            logger.info("Backend PTT listener active (%s)", ctx.config.audio.ptt_key_name)
        except Exception as exc:
            logger.warning("Backend PTT listener skipped: %s", exc)

    hot: object | None = None
    wd_task: asyncio.Task[None] | None = None

    async def on_hibernation() -> None:
        repo = SystemStateRepository(ctx.db_path)
        await repo.set_value("last_hibernation_wall", str(int(time.time())))
        for sid in ctx.websocket_manager.iter_session_ids():
            await ctx.websocket_manager.send_to_session(
                sid,
                "system_state",
                {"state": "resumed_after_hibernate", "health": "degraded"},
            )

    watchdog = SessionWatchdog(
        db_path=ctx.db_path,
        llm_client=ctx.llm_client,
        on_hibernation=on_hibernation,
    )
    wd_task = asyncio.create_task(watchdog.run_forever())

    try:
        hot = start_hot_reload(ctx, app)
    except Exception as exc:
        logger.warning("Hot-reload watcher not started: %s", exc)

    if ctx.game_observer is not None:
        ctx.game_observer._emit = make_game_emitter(ctx)
        await ctx.game_observer.start()
    if ctx.observer_loop is not None:
        await ctx.observer_loop.start()

    try:
        yield
    finally:
        if ptt_listener is not None:
            try:
                ptt_listener.stop()
            except Exception:
                logger.debug("PTT listener stop failed", exc_info=True)
        watchdog.stop()
        if wd_task is not None:
            wd_task.cancel()
            try:
                await wd_task
            except asyncio.CancelledError:
                pass
        if hot is not None:
            hot.stop()
        if ctx.game_observer is not None:
            await ctx.game_observer.stop()
        if ctx.observer_loop is not None:
            await ctx.observer_loop.stop()
        try:
            await ctx.llm_client.aclose()
        except Exception as exc:  # pragma: no cover
            logger.debug("llm client close: %s", exc)
        kw = getattr(ctx, "knowledge_watcher", None)
        if kw is not None:
            try:
                kw.stop()
            except Exception as exc_kw:
                logger.debug("knowledge watcher stop: %s", exc_kw)


app = FastAPI(
    title="Assystent Backend",

    description="Local AI gaming companion with 3D avatar",
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(api_router, prefix="/api/v1")


@app.websocket("/ws")
async def multiplexed_socket(ws: WebSocket):
    await websocket_endpoint(ws, app)


@app.get("/")
async def root():
    return {"message": "Assystent Backend is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
