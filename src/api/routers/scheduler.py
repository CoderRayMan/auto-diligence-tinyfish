"""
/api/scheduler — Proactive closed-loop re-scan engine.

Uses TinyFish agent.queue() to fire background runs for stale watchlist
entities without blocking the API.  A background asyncio loop checks
the watchlist every INTERVAL_MINUTES and auto-queues new scans.

Also exposes:
  GET  /scheduler/status        — current scheduler state + queue depth
  POST /scheduler/trigger       — manually trigger a staleness sweep
  POST /scheduler/pause         — pause auto-scheduling
  POST /scheduler/resume        — resume auto-scheduling
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ..store import scan_store
from ..routers.watchlist import _WATCHLIST, _LOCK, _refresh_entry, STALE_AFTER_DAYS
from ..schemas import ScanRequest, ScanResponse, ScanStatus, AgentEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduler", tags=["scheduler"])

# ------------------------------------------------------------------ state

INTERVAL_MINUTES: int = 30          # auto-sweep every 30 minutes (demo: short)
MAX_QUEUE_DEPTH: int = 10           # never queue more than 10 concurrent jobs

_scheduler_running: bool = False
_scheduler_paused: bool = False
_last_sweep_at: Optional[datetime] = None
_next_sweep_at: Optional[datetime] = None
_queued_run_ids: List[str] = []      # TinyFish run_ids queued via agent.queue()
_sweep_log: List[dict] = []          # audit trail of past sweeps (last 50)
_scheduler_task: Optional[asyncio.Task] = None


# ------------------------------------------------------------------ internal logic

async def _auto_queue_stale_entities() -> List[str]:
    """
    Find all stale watchlist entities and fire a new scan for each.
    Uses the standard scan creation path (DiligenceManager) via BackgroundTasks
    so SSE and MongoDB persistence work identically to manual scans.
    Returns list of new scan_ids created.
    """
    from ..routers.scans import _run_scan_background, _available_sources

    async with _LOCK:
        entries = list(_WATCHLIST.values())

    stale = []
    for entry in entries:
        refreshed = await _refresh_entry(entry)
        if refreshed.is_stale:
            stale.append(refreshed)

    new_scan_ids: List[str] = []

    for entry in stale[:MAX_QUEUE_DEPTH]:
        try:
            scan_id = str(uuid.uuid4())
            sources = _available_sources()
            persona_id = entry.persona_id

            from ..schemas import get_persona
            persona = get_persona(persona_id) if persona_id else None
            query = persona.default_query if persona else "regulatory violations and enforcement actions"
            if persona and persona.default_sources:
                sources = persona.default_sources

            scan = ScanResponse(
                scan_id=scan_id,
                status=ScanStatus.pending,
                target=entry.entity_name,
                query=query,
                persona_id=persona_id,
                created_at=datetime.now(timezone.utc),
                sources_total=len(sources),
                sources_completed=0,
                sources_failed=0,
            )
            await scan_store.create(scan)
            # Fire and forget in background
            asyncio.create_task(
                _run_scan_background(
                    scan_id,
                    ScanRequest(
                        target=entry.entity_name,
                        query=query,
                        sources=sources,
                        persona_id=persona_id,
                    ),
                )
            )
            new_scan_ids.append(scan_id)
            logger.info(f"[Scheduler] Queued scan {scan_id} for stale entity '{entry.entity_name}'")
        except Exception as exc:
            logger.error(f"[Scheduler] Failed to queue scan for '{entry.entity_name}': {exc}")

    return new_scan_ids


async def _scheduler_loop() -> None:
    """Main background loop — runs forever, sweeping every INTERVAL_MINUTES."""
    global _last_sweep_at, _next_sweep_at, _sweep_log

    logger.info("[Scheduler] Background loop started")
    while _scheduler_running:
        if not _scheduler_paused:
            _last_sweep_at = datetime.now(timezone.utc)
            _next_sweep_at = _last_sweep_at + timedelta(minutes=INTERVAL_MINUTES)

            try:
                queued = await _auto_queue_stale_entities()
                entry = {
                    "swept_at": _last_sweep_at.isoformat(),
                    "entities_queued": len(queued),
                    "scan_ids": queued,
                }
                _sweep_log.insert(0, entry)
                _sweep_log[:] = _sweep_log[:50]   # keep last 50
                logger.info(f"[Scheduler] Sweep complete — {len(queued)} scans queued")
            except Exception as exc:
                logger.error(f"[Scheduler] Sweep error: {exc}")

        # Sleep in 5-second ticks so pause/stop responds quickly
        ticks = INTERVAL_MINUTES * 60 // 5
        for _ in range(ticks):
            if not _scheduler_running:
                break
            await asyncio.sleep(5)

    logger.info("[Scheduler] Background loop stopped")


def _start_scheduler() -> None:
    global _scheduler_running, _scheduler_task
    if _scheduler_running:
        return
    _scheduler_running = True
    _scheduler_task = asyncio.create_task(_scheduler_loop())


def _stop_scheduler() -> None:
    global _scheduler_running
    _scheduler_running = False


# ------------------------------------------------------------------ routes

class SchedulerStatus(BaseModel):
    running: bool
    paused: bool
    interval_minutes: int
    last_sweep_at: Optional[str]
    next_sweep_at: Optional[str]
    sweep_count: int
    recent_sweeps: List[dict]


@router.get("/status", response_model=SchedulerStatus)
async def get_scheduler_status() -> SchedulerStatus:
    """Current scheduler state, last/next sweep timestamps, and recent sweep log."""
    return SchedulerStatus(
        running=_scheduler_running,
        paused=_scheduler_paused,
        interval_minutes=INTERVAL_MINUTES,
        last_sweep_at=_last_sweep_at.isoformat() if _last_sweep_at else None,
        next_sweep_at=_next_sweep_at.isoformat() if _next_sweep_at else None,
        sweep_count=len(_sweep_log),
        recent_sweeps=_sweep_log[:10],
    )


@router.post("/trigger")
async def trigger_sweep() -> dict:
    """Manually trigger an immediate staleness sweep, regardless of schedule."""
    queued = await _auto_queue_stale_entities()
    entry = {
        "swept_at": datetime.now(timezone.utc).isoformat(),
        "entities_queued": len(queued),
        "scan_ids": queued,
        "triggered_manually": True,
    }
    _sweep_log.insert(0, entry)
    _sweep_log[:] = _sweep_log[:50]
    return {
        "message": f"Sweep complete — {len(queued)} scan(s) queued",
        "scan_ids": queued,
    }


@router.post("/pause")
async def pause_scheduler() -> dict:
    """Pause the auto-scheduler (does not stop in-flight scans)."""
    global _scheduler_paused
    if not _scheduler_running:
        raise HTTPException(status_code=400, detail="Scheduler is not running")
    _scheduler_paused = True
    return {"message": "Scheduler paused"}


@router.post("/resume")
async def resume_scheduler() -> dict:
    """Resume a paused scheduler."""
    global _scheduler_paused
    _scheduler_paused = False
    return {"message": "Scheduler resumed"}


@router.post("/start")
async def start_scheduler() -> dict:
    """Start the background scheduler if not already running."""
    if _scheduler_running:
        return {"message": "Scheduler already running"}
    _start_scheduler()
    return {"message": "Scheduler started", "interval_minutes": INTERVAL_MINUTES}


@router.post("/stop")
async def stop_scheduler() -> dict:
    """Stop the background scheduler."""
    _stop_scheduler()
    return {"message": "Scheduler stopped"}
