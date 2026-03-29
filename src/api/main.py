"""
AutoDiligence FastAPI application.

Run with:
    uvicorn src.api.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()  # Load .env before any SDK/config imports

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import scans_router, findings_router, agents_router, personas_router, watchlist_router, analytics_router, scheduler_router, runs_router, digest_router
from .store import scan_store

logger = logging.getLogger(__name__)

_START_TIME = datetime.utcnow()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .store import scan_store
    from .routers.scheduler import _start_scheduler
    await scan_store.connect()   # raises RuntimeError if connection fails
    _start_scheduler()           # begin proactive re-scan loop
    yield
    from .routers.scheduler import _stop_scheduler
    _stop_scheduler()
    await scan_store.disconnect()


app = FastAPI(
    title="AutoDiligence API",
    description="Multi-Agent Regulatory Research Engine powered by TinyFish",
    version="0.1.0",
    lifespan=lifespan,
)

_allowed_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:5174,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:5174",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)

app.include_router(scans_router, prefix="/api")
app.include_router(findings_router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(personas_router, prefix="/api")
app.include_router(watchlist_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(scheduler_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
app.include_router(digest_router, prefix="/api")


@app.get("/api/health")
async def health() -> dict:
    uptime_s = int((datetime.utcnow() - _START_TIME).total_seconds())
    scans = await scan_store.list_all()
    completed = sum(1 for s in scans if s.status == "completed")
    running = sum(1 for s in scans if s.status in ("running", "pending"))
    return {
        "status": "ok",
        "service": "autodiligence",
        "version": "1.0.0",
        "uptime_seconds": uptime_s,
        "store": "mongodb",
        "store_healthy": True,
        "stats": {
            "total_scans": len(scans),
            "completed_scans": completed,
            "active_scans": running,
        },
    }
