"""FastAPI application entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import init_db
from app.routers import auth, chat, evaluations, graph, projects, settings, shares, trials
from app.services.sync import start_sync

logger = logging.getLogger(__name__)

_sync_task: asyncio.Task | None = None


async def _auto_sync_loop() -> None:
    """Background loop that triggers sync at configured intervals."""
    while True:
        s = get_settings()
        interval = s.sync_interval_minutes
        if interval and interval > 0:
            logger.info("Auto-sync: triggering sync (interval=%d min)", interval)
            start_sync()
            await asyncio.sleep(interval * 60)
        else:
            await asyncio.sleep(60)


async def restart_auto_sync_task(interval_minutes: int) -> None:
    """Restart the auto-sync task with new interval."""
    global _sync_task

    # Cancel existing task
    if _sync_task and not _sync_task.done():
        _sync_task.cancel()
        try:
            await _sync_task
        except asyncio.CancelledError:
            pass
        logger.info("Auto-sync task cancelled")

    # Start new task if interval > 0
    if interval_minutes and interval_minutes > 0:
        _sync_task = asyncio.create_task(_auto_sync_loop())
        logger.info("Auto-sync task started (interval=%d min)", interval_minutes)
    else:
        _sync_task = None
        logger.info("Auto-sync disabled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _sync_task
    init_db()

    s = get_settings()
    if s.sync_interval_minutes and s.sync_interval_minutes > 0:
        _sync_task = asyncio.create_task(_auto_sync_loop())

    yield

    if _sync_task:
        _sync_task.cancel()


app = FastAPI(title="AI Radar", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(evaluations.router, prefix="/api/evaluations", tags=["evaluations"])
app.include_router(trials.router, prefix="/api/trials", tags=["trials"])
app.include_router(shares.router, prefix="/api/shares", tags=["shares"])
app.include_router(graph.router, prefix="/api/graph", tags=["graph"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
