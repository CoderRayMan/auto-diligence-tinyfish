"""
In-memory scan store.  In production this would be replaced with a
persistent database, but for the hackathon/demo it's sufficient.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from .schemas import ScanResponse, ScanStatus, Finding, AgentEvent


class ScanStore:
    """Thread-safe in-memory store for scan state, findings, and SSE event queues."""

    def __init__(self) -> None:
        self._scans: Dict[str, ScanResponse] = {}
        self._findings: Dict[str, List[Finding]] = {}
        # Each scan gets an asyncio Queue for SSE events; keyed by scan_id
        self._event_queues: Dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ scans
    async def create(self, scan: ScanResponse) -> None:
        async with self._lock:
            self._scans[scan.scan_id] = scan
            self._findings[scan.scan_id] = []
            self._event_queues[scan.scan_id] = asyncio.Queue(maxsize=500)

    async def get(self, scan_id: str) -> Optional[ScanResponse]:
        return self._scans.get(scan_id)

    async def list_all(self) -> List[ScanResponse]:
        return list(self._scans.values())

    async def update(self, scan_id: str, **kwargs: Any) -> Optional[ScanResponse]:
        async with self._lock:
            scan = self._scans.get(scan_id)
            if scan is None:
                return None
            updated = scan.model_copy(update=kwargs)
            self._scans[scan_id] = updated
            return updated

    # --------------------------------------------------------------- findings
    async def add_findings(self, scan_id: str, findings: List[Finding]) -> None:
        async with self._lock:
            if scan_id in self._findings:
                self._findings[scan_id].extend(findings)

    def get_findings(self, scan_id: str) -> List[Finding]:
        return list(self._findings.get(scan_id, []))

    # ------------------------------------------------------------------ events
    async def push_event(self, event: AgentEvent) -> None:
        q = self._event_queues.get(event.scan_id)
        if q is not None:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest event to make room
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except asyncio.QueueEmpty:
                    pass

    async def get_event_queue(self, scan_id: str) -> Optional[asyncio.Queue]:
        return self._event_queues.get(scan_id)

    async def close_event_queue(self, scan_id: str) -> None:
        """Signal SSE consumers that this scan is done (sentinel None)."""
        q = self._event_queues.get(scan_id)
        if q is not None:
            await q.put(None)


# Application-wide singleton
scan_store = ScanStore()
