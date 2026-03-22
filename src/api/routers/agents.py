"""
/api/agents — SSE stream for live agent activity log.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from ..schemas import AgentEvent
from ..store import scan_store

router = APIRouter(prefix="/agents", tags=["agents"])


async def _event_generator(scan_id: str) -> AsyncGenerator[dict, None]:
    """Async generator that yields SSE dicts from the scan's event queue."""
    q = await scan_store.get_event_queue(scan_id)
    if q is None:
        return

    while True:
        try:
            event: Optional[AgentEvent] = await asyncio.wait_for(q.get(), timeout=30.0)
        except asyncio.TimeoutError:
            # Keep-alive ping
            yield {"event": "ping", "data": ""}
            continue

        if event is None:
            # Sentinel — scan finished
            yield {"event": "done", "data": json.dumps({"scan_id": scan_id})}
            break

        yield {
            "event": "agent_event",
            "data": event.model_dump_json(),
        }


@router.get("/stream")
async def stream_agent_events(
    scan_id: str = Query(..., description="Scan ID to subscribe to"),
) -> EventSourceResponse:
    """
    SSE endpoint.  Connect to receive live agent log events for a scan.
    The stream ends with a 'done' event when the scan completes.
    """
    scan = await scan_store.get(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    return EventSourceResponse(_event_generator(scan_id))


@router.get("/status")
async def agent_status(
    scan_id: str = Query(..., description="Scan ID to get agent snapshot for"),
) -> dict:
    """Return a snapshot of source completion status for a scan."""
    scan = await scan_store.get(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    return {
        "scan_id": scan_id,
        "status": scan.status,
        "sources_total": scan.sources_total,
        "sources_completed": scan.sources_completed,
        "sources_failed": scan.sources_failed,
        "source_results": [r.model_dump() for r in scan.source_results],
    }
