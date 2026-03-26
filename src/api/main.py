"""
AutoDiligence FastAPI application.

Run with:
    uvicorn src.api.main:app --reload --port 8000
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()  # Load .env before any SDK/config imports

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import scans_router, findings_router, agents_router, personas_router
from .store import scan_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create MongoDB indexes (no-op for in-memory store)
    await scan_store.ensure_indexes()
    mongo_ok = await scan_store.ping()
    print(f"[startup] Store ping: {'OK' if mongo_ok else 'FAILED'}")
    yield
    # Shutdown: close MongoDB client
    scan_store.close()


app = FastAPI(
    title="AutoDiligence API",
    description="Multi-Agent Regulatory Research Engine powered by TinyFish",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow the Vite dev server and any same-origin production deploy
_allowed_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:5174,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:5174",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)

# Register routers under /api prefix
app.include_router(scans_router, prefix="/api")
app.include_router(findings_router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(personas_router, prefix="/api")


@app.get("/api/health")
async def health() -> dict:
    mongo_ok = await scan_store.ping()
    return {
        "status": "ok" if mongo_ok else "degraded",
        "service": "autodiligence",
        "store": "mongodb" if mongo_ok else "unknown",
        "store_healthy": mongo_ok,
    }
