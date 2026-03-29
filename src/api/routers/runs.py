"""
/api/runs — TinyFish Run Audit Trail.

Exposes the TinyFish runs.list() and runs.get() APIs directly so analysts
can inspect every browser agent run ever fired — including goal text,
step count, timing, live streaming_url, and structured result.

Endpoints:
  GET  /runs                  — paginated list of all TinyFish runs
  GET  /runs/{run_id}         — full detail for one run
  GET  /runs/stats            — aggregate timing + success rate telemetry
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["runs"])


# ------------------------------------------------------------------ helpers

def _get_client():
    """Lazily instantiate TinyFish client (needs TINYFISH_API_KEY in env)."""
    from tinyfish import TinyFish
    api_key = os.getenv("TINYFISH_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="TINYFISH_API_KEY not configured")
    return TinyFish(api_key=api_key)


# ------------------------------------------------------------------ response models

class RunSummary(BaseModel):
    run_id: str
    status: str
    goal_preview: str           # first 120 chars of goal
    created_at: Optional[str]
    started_at: Optional[str]
    finished_at: Optional[str]
    duration_seconds: Optional[float]
    streaming_url: Optional[str]
    has_result: bool
    error_message: Optional[str]


class RunDetail(BaseModel):
    run_id: str
    status: str
    goal: str
    created_at: Optional[str]
    started_at: Optional[str]
    finished_at: Optional[str]
    duration_seconds: Optional[float]
    streaming_url: Optional[str]
    result: Optional[dict]
    error_message: Optional[str]
    error_category: Optional[str]
    proxy_enabled: Optional[bool]
    proxy_country: Optional[str]


class RunStats(BaseModel):
    total_runs: int
    completed: int
    failed: int
    pending_or_running: int
    success_rate_pct: float
    avg_duration_seconds: Optional[float]
    total_goals_fired: int


# ------------------------------------------------------------------ routes

@router.get("/stats", response_model=RunStats)
async def get_run_stats(
    limit: int = Query(default=100, ge=1, le=500, description="How many recent runs to analyse"),
) -> RunStats:
    """
    Aggregate telemetry over the most recent TinyFish runs.
    Shows success rate, average duration, and run status distribution.
    Uses client.runs.list() with pagination.
    """
    import asyncio
    client = _get_client()

    try:
        resp = await asyncio.to_thread(client.runs.list, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TinyFish API error: {exc}")

    runs = resp.data
    completed = [r for r in runs if r.status.value == "COMPLETED"]
    failed = [r for r in runs if r.status.value == "FAILED"]
    active = [r for r in runs if r.status.value in ("PENDING", "RUNNING")]

    durations = []
    for r in completed:
        if r.started_at and r.finished_at:
            durations.append((r.finished_at - r.started_at).total_seconds())

    return RunStats(
        total_runs=len(runs),
        completed=len(completed),
        failed=len(failed),
        pending_or_running=len(active),
        success_rate_pct=round(len(completed) / len(runs) * 100, 1) if runs else 0.0,
        avg_duration_seconds=round(sum(durations) / len(durations), 1) if durations else None,
        total_goals_fired=len(runs),
    )


@router.get("", response_model=dict)
async def list_runs(
    status: Optional[str] = Query(default=None, description="Filter by status: PENDING|RUNNING|COMPLETED|FAILED|CANCELLED"),
    goal: Optional[str] = Query(default=None, description="Filter by goal text substring"),
    created_after: Optional[str] = Query(default=None, description="ISO datetime lower bound"),
    created_before: Optional[str] = Query(default=None, description="ISO datetime upper bound"),
    limit: int = Query(default=25, ge=1, le=100),
    cursor: Optional[str] = Query(default=None, description="Pagination cursor"),
) -> dict:
    """
    List TinyFish agent runs with optional filters.
    Uses the full runs.list() API with cursor-based pagination.
    """
    import asyncio
    from tinyfish.runs.types import RunStatus, SortDirection

    client = _get_client()

    # Map status string → RunStatus enum
    status_enum = None
    if status:
        try:
            status_enum = RunStatus(status.upper())
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status '{status}'")

    try:
        resp = await asyncio.to_thread(
            client.runs.list,
            status=status_enum,
            goal=goal,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
            cursor=cursor,
            sort_direction=SortDirection.DESC if hasattr(SortDirection, "DESC") else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TinyFish API error: {exc}")

    summaries = []
    for r in resp.data:
        duration = None
        if r.started_at and r.finished_at:
            duration = round((r.finished_at - r.started_at).total_seconds(), 1)
        summaries.append(RunSummary(
            run_id=r.run_id,
            status=r.status.value,
            goal_preview=(r.goal or "")[:120],
            created_at=r.created_at.isoformat() if r.created_at else None,
            started_at=r.started_at.isoformat() if r.started_at else None,
            finished_at=r.finished_at.isoformat() if r.finished_at else None,
            duration_seconds=duration,
            streaming_url=r.streaming_url,
            has_result=r.result is not None,
            error_message=r.error.message if r.error else None,
        ).model_dump())

    return {
        "runs": summaries,
        "total": resp.pagination.total,
        "has_more": resp.pagination.has_more,
        "next_cursor": resp.pagination.next_cursor,
    }


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: str) -> RunDetail:
    """
    Retrieve full detail for a single TinyFish run including result JSON,
    streaming URL, step count, and error details.
    Uses client.runs.get(run_id).
    """
    import asyncio
    client = _get_client()

    try:
        r = await asyncio.to_thread(client.runs.get, run_id)
    except Exception as exc:
        if "404" in str(exc) or "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        raise HTTPException(status_code=502, detail=f"TinyFish API error: {exc}")

    duration = None
    if r.started_at and r.finished_at:
        duration = round((r.finished_at - r.started_at).total_seconds(), 1)

    return RunDetail(
        run_id=r.run_id,
        status=r.status.value,
        goal=r.goal,
        created_at=r.created_at.isoformat() if r.created_at else None,
        started_at=r.started_at.isoformat() if r.started_at else None,
        finished_at=r.finished_at.isoformat() if r.finished_at else None,
        duration_seconds=duration,
        streaming_url=r.streaming_url,
        result=r.result,
        error_message=r.error.message if r.error else None,
        error_category=r.error.category.value if r.error and r.error.category else None,
        proxy_enabled=r.browser_config.proxy_enabled if r.browser_config else None,
        proxy_country=r.browser_config.proxy_country_code if r.browser_config else None,
    )
