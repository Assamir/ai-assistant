"""
Main entry point for the Assystent backend service.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket

from backend.api.app_context import create_app_context, make_game_emitter
from backend.api.routes import router as api_router
from backend.api.ws_router import websocket_endpoint
from backend.db.repositories import SystemStateRepository
from backend.services.config_hot_reload import start_hot_reload
from backend.services.session_watchdog import SessionWatchdog

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ctx = create_app_context()
    app.state.ctx = ctx

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

    try:
        yield
    finally:
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
        try:
            await ctx.llm_client.aclose()
        except Exception as exc:  # pragma: no cover
            logger.debug("llm client close: %s", exc)


app = FastAPI(
    title="Assystent Backend",

    description="Local AI gaming companion with 3D avatar",
    version="0.4.0",
    lifespan=lifespan,
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
