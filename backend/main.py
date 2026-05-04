"""
Main entry point for the Assystent backend service.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket

from backend.api.app_context import create_app_context
from backend.api.routes import router as api_router
from backend.api.ws_router import websocket_endpoint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ctx = create_app_context()
    app.state.ctx = ctx


    try:
        yield
    finally:


        try:


            await ctx.llm_client.aclose()
        except Exception as exc:  # pragma: no cover
            logger.debug("llm client close: %s", exc)


app = FastAPI(
    title="Assystent Backend",

    description="Local AI gaming companion with 3D avatar",
    version="0.3.0",
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
