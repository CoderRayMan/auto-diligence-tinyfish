"""
/api/scans — Start and query diligence scans.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import Response

from ..schemas import (
    ScanRequest,
    ScanResponse,
    ScanStatus,
    SourceResult,
    Finding,
    AgentEvent,
)
from ..store import scan_store

router = APIRouter(prefix="/scans", tags=["scans"])


# ------------------------------------------------------------------ helpers

def _available_sources() -> List[str]:
    """Return the full list of configured source IDs."""
    return ["us_osha", "us_fda", "us_sec", "us_dol", "us_epa"]


async def _run_scan_background(scan_id: str, request: ScanRequest) -> None:
    """Background coroutine that drives the DiligenceManager and updates the store."""
    from ...manager import DiligenceManager
    from ...utils.risk_scorer import ResultAggregator, DiligenceFinding

    sources = request.sources or _available_sources()

    # Update status to running
    await scan_store.update(scan_id, status=ScanStatus.running)

    # Emit "RUNNING" event per source at start
    now = datetime.utcnow().isoformat()
    for src in sources:
        await scan_store.push_event(
            AgentEvent(
                scan_id=scan_id,
                source_id=src,
                agent_tag="RUNNING",
                message=f"Agent starting for source: {src}",
                timestamp=now,
            )
        )

    manager = DiligenceManager(
        sources=sources,
        max_concurrent_agents=request.max_concurrent_agents,
        use_token_vault=True,
    )

    # Build a thread-safe SSE callback that bridges TinyFish PROGRESS events
    # into the asyncio SSE queue.  agent.research() runs inside asyncio.to_thread()
    # so we capture the running event loop here and use run_coroutine_threadsafe.
    loop = asyncio.get_event_loop()

    def _sse_event(source_id: str, tag: str, message: str, streaming_url: str | None = None) -> None:
        """Called from the TinyFish stream thread; pushes to the async SSE queue."""
        asyncio.run_coroutine_threadsafe(
            scan_store.push_event(
                AgentEvent(
                    scan_id=scan_id,
                    source_id=source_id,
                    agent_tag=tag,
                    message=message,
                    timestamp=datetime.utcnow().isoformat(),
                    streaming_url=streaming_url,
                )
            ),
            loop,
        )

    source_results: List[SourceResult] = []
    all_raw: dict = {}

    try:
        results = await manager.research(
            target=request.target,
            query=request.query,
            event_callback=_sse_event,
        )

        for source_id, result in results.items():
            ts = datetime.utcnow().isoformat()
            tag = "COMPLETED" if result.status == "completed" else "FAILED"
            msg = (
                f"Found {len(result.data)} records"
                if result.status == "completed"
                else f"Failed: {result.error}"
            )
            await scan_store.push_event(
                AgentEvent(
                    scan_id=scan_id,
                    source_id=source_id,
                    agent_tag=tag,
                    message=msg,
                    timestamp=ts,
                )
            )
            source_results.append(
                SourceResult(
                    source_id=source_id,
                    status=result.status,
                    records_found=len(result.data),
                    execution_time_s=round(result.execution_time, 2),
                    error=result.error,
                )
            )
            if result.status == "completed":
                all_raw[source_id] = {"status": "completed", "cases": result.data}

        # Aggregate and score
        diligence_findings = ResultAggregator.aggregate_all(all_raw)
        risk = ResultAggregator.compute_risk_score(diligence_findings)

        # Convert to API Finding objects
        api_findings: List[Finding] = [
            Finding(
                finding_id=f.finding_id,
                scan_id=scan_id,
                source_id=f.source_id,
                case_id=f.case_id,
                case_type=f.case_type,
                entity_name=f.entity_name,
                violation_type=f.violation_type,
                decision_date=f.decision_date,
                penalty_amount=f.penalty_amount,
                severity=f.severity,
                status=f.status if f.status in ("open", "settled", "closed", "appealed") else "unknown",
                description=f.description,
                source_url=f.source_url,
                jurisdiction=f.jurisdiction,
            )
            for f in diligence_findings
        ]

        await scan_store.add_findings(scan_id, api_findings)
        await scan_store.update(
            scan_id,
            status=ScanStatus.completed,
            completed_at=datetime.utcnow(),
            sources_total=len(sources),
            sources_completed=sum(1 for r in source_results if r.status == "completed"),
            sources_failed=sum(1 for r in source_results if r.status == "failed"),
            risk_score=risk["score"],
            risk_label=risk["label"],
            findings_count=len(api_findings),
            source_results=source_results,
        )

    except Exception as exc:
        await scan_store.update(
            scan_id,
            status=ScanStatus.failed,
            completed_at=datetime.utcnow(),
            source_results=source_results,
        )
        await scan_store.push_event(
            AgentEvent(
                scan_id=scan_id,
                source_id="manager",
                agent_tag="FAILED",
                message=str(exc),
                timestamp=datetime.utcnow().isoformat(),
            )
        )
    finally:
        await manager.close()
        await scan_store.close_event_queue(scan_id)


# ------------------------------------------------------------------ routes

@router.post("", response_model=ScanResponse, status_code=202)
async def create_scan(request: ScanRequest, background_tasks: BackgroundTasks) -> ScanResponse:
    """Start a new diligence scan. Returns immediately; poll GET /scans/{id} for status."""
    scan_id = str(uuid.uuid4())
    sources = request.sources or _available_sources()

    scan = ScanResponse(
        scan_id=scan_id,
        status=ScanStatus.pending,
        target=request.target,
        created_at=datetime.utcnow(),
        sources_total=len(sources),
        sources_completed=0,
        sources_failed=0,
    )
    await scan_store.create(scan)
    background_tasks.add_task(_run_scan_background, scan_id, request)
    return scan


@router.get("", response_model=List[ScanResponse])
async def list_scans() -> List[ScanResponse]:
    """List all scans in reverse chronological order."""
    scans = await scan_store.list_all()
    return sorted(scans, key=lambda s: s.created_at, reverse=True)


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(scan_id: str) -> ScanResponse:
    """Get the current status and summary for a scan."""
    scan = await scan_store.get(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@router.delete("/{scan_id}", status_code=204)
async def cancel_scan(scan_id: str) -> None:
    """Mark a scan as cancelled. Does not interrupt in-flight agents."""
    scan = await scan_store.get(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.status in (ScanStatus.completed, ScanStatus.failed, ScanStatus.cancelled):
        return
    await scan_store.update(scan_id, status=ScanStatus.cancelled)
    await scan_store.close_event_queue(scan_id)
