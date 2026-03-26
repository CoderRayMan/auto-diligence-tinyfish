"""
Scan store factory.

If MONGODB_URI is set the application uses a persistent MongoDB store
(via Motor); otherwise it falls back to the original in-memory store.

Both backends implement the same interface so the rest of the app
doesn't need to know which one is active.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from .schemas import ScanResponse, ScanStatus, Finding, AgentEvent


# ────────────────────────────────────────────────────────────────────
# In-memory implementation (unchanged from the original)
# ────────────────────────────────────────────────────────────────────

class InMemoryScanStore:
    """Thread-safe in-memory store for scan state, findings, and SSE event queues."""

    def __init__(self) -> None:
        self._scans: Dict[str, ScanResponse] = {}
        self._findings: Dict[str, List[Finding]] = {}
        self._event_queues: Dict[str, asyncio.Queue] = {}
        self._event_history: Dict[str, List[AgentEvent]] = {}
        self._lock = asyncio.Lock()

    # --- lifecycle helpers (no-ops for in-memory) ---
    async def ensure_indexes(self) -> None:
        pass

    async def ping(self) -> bool:
        return True

    def close(self) -> None:
        pass

    # --- scans ---
    async def create(self, scan: ScanResponse) -> None:
        async with self._lock:
            self._scans[scan.scan_id] = scan
            self._findings[scan.scan_id] = []
            self._event_queues[scan.scan_id] = asyncio.Queue(maxsize=500)
            self._event_history[scan.scan_id] = []

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

    # --- findings ---
    async def add_findings(self, scan_id: str, findings: List[Finding]) -> None:
        async with self._lock:
            if scan_id in self._findings:
                self._findings[scan_id].extend(findings)

    def get_findings(self, scan_id: str) -> List[Finding]:
        return list(self._findings.get(scan_id, []))

    async def get_findings_async(self, scan_id: str) -> List[Finding]:
        return self.get_findings(scan_id)

    # --- events ---
    async def push_event(self, event: AgentEvent) -> None:
        history = self._event_history.get(event.scan_id)
        if history is not None:
            history.append(event)
        q = self._event_queues.get(event.scan_id)
        if q is not None:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except asyncio.QueueEmpty:
                    pass

    async def get_event_queue(self, scan_id: str) -> Optional[asyncio.Queue]:
        return self._event_queues.get(scan_id)

    def get_event_history(self, scan_id: str) -> List[AgentEvent]:
        return list(self._event_history.get(scan_id, []))

    async def get_event_history_async(self, scan_id: str) -> List[AgentEvent]:
        return self.get_event_history(scan_id)

    async def close_event_queue(self, scan_id: str) -> None:
        q = self._event_queues.get(scan_id)
        if q is not None:
            await q.put(None)


# ────────────────────────────────────────────────────────────────────
# Factory — choose backend at import time
# ────────────────────────────────────────────────────────────────────

def _create_store():
    """Return MongoScanStore if MONGODB_URI is configured, else in-memory."""
    from dotenv import load_dotenv
    load_dotenv()

    uri = os.getenv("MONGODB_URI", "").strip()
    if uri:
        from .mongo_store import MongoScanStore
        print(f"[store] Using MongoDB store  (db={os.getenv('MONGODB_DB', 'autodiligence')})")
        return MongoScanStore()
    else:
        print("[store] Using in-memory store (MONGODB_URI not set)")
        return InMemoryScanStore()


scan_store = _create_store()
