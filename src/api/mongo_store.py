"""
MongoDB-backed scan store.

Replaces the in-memory ScanStore with persistent storage using Motor
(async MongoDB driver).  The SSE event queues remain in-memory because
they are ephemeral real-time channels; only the *history* is persisted.

Collections
-----------
- scans       : one document per scan (ScanResponse as dict)
- findings    : one document per finding, indexed by scan_id
- agent_events: one document per event, indexed by scan_id
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .schemas import ScanResponse, ScanStatus, Finding, AgentEvent


class MongoScanStore:
    """Persistent scan store backed by MongoDB Atlas via Motor."""

    def __init__(self) -> None:
        uri = os.getenv("MONGODB_URI", "")
        db_name = os.getenv("MONGODB_DB", "autodiligence")

        if not uri:
            raise RuntimeError(
                "MONGODB_URI environment variable is not set. "
                "Set it in .env to your MongoDB connection string."
            )

        self._client: AsyncIOMotorClient = AsyncIOMotorClient(uri)
        self._db: AsyncIOMotorDatabase = self._client[db_name]

        # Collections
        self._scans = self._db["scans"]
        self._findings_col = self._db["findings"]
        self._events_col = self._db["agent_events"]

        # In-memory SSE queues (ephemeral; not persisted)
        self._event_queues: Dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()

    # ─── Indexes (call once at startup) ──────────────────────────────

    async def ensure_indexes(self) -> None:
        """Create indexes for fast lookups."""
        await self._scans.create_index("scan_id", unique=True)
        await self._findings_col.create_index("scan_id")
        await self._findings_col.create_index("finding_id")
        await self._events_col.create_index("scan_id")

    # ─── Scans ───────────────────────────────────────────────────────

    async def create(self, scan: ScanResponse) -> None:
        doc = scan.model_dump(mode="json")
        doc["_id"] = scan.scan_id  # use scan_id as _id
        await self._scans.insert_one(doc)
        # Prepare in-memory SSE queue
        async with self._lock:
            self._event_queues[scan.scan_id] = asyncio.Queue(maxsize=500)

    async def get(self, scan_id: str) -> Optional[ScanResponse]:
        doc = await self._scans.find_one({"scan_id": scan_id})
        if doc is None:
            return None
        doc.pop("_id", None)
        return ScanResponse(**doc)

    async def list_all(self) -> List[ScanResponse]:
        scans: List[ScanResponse] = []
        async for doc in self._scans.find().sort("created_at", -1):
            doc.pop("_id", None)
            try:
                scans.append(ScanResponse(**doc))
            except Exception:
                pass  # skip corrupt documents
        return scans

    async def update(self, scan_id: str, **kwargs: Any) -> Optional[ScanResponse]:
        if not kwargs:
            return await self.get(scan_id)

        # Serialize enum values and datetimes for Mongo
        update_doc: Dict[str, Any] = {}
        for k, v in kwargs.items():
            if isinstance(v, ScanStatus):
                update_doc[k] = v.value
            elif isinstance(v, datetime):
                update_doc[k] = v.isoformat()
            elif isinstance(v, list) and v and hasattr(v[0], "model_dump"):
                update_doc[k] = [item.model_dump(mode="json") for item in v]
            else:
                update_doc[k] = v

        result = await self._scans.find_one_and_update(
            {"scan_id": scan_id},
            {"$set": update_doc},
            return_document=True,
        )
        if result is None:
            return None
        result.pop("_id", None)
        return ScanResponse(**result)

    # ─── Findings ────────────────────────────────────────────────────

    async def add_findings(self, scan_id: str, findings: List[Finding]) -> None:
        if not findings:
            return
        docs = []
        for f in findings:
            doc = f.model_dump(mode="json")
            doc["_scan_id"] = scan_id  # redundant but useful for queries
            docs.append(doc)
        await self._findings_col.insert_many(docs)

    def get_findings(self, scan_id: str) -> List[Finding]:
        """Synchronous wrapper — use get_findings_async where possible."""
        # This is called from sync contexts in findings router.
        # We return a coroutine-launcher that the caller can await or
        # we use a blocking fallback.
        raise RuntimeError(
            "Use get_findings_async() instead. "
            "The sync get_findings() is not supported with MongoScanStore."
        )

    async def get_findings_async(self, scan_id: str) -> List[Finding]:
        findings: List[Finding] = []
        async for doc in self._findings_col.find({"scan_id": scan_id}):
            doc.pop("_id", None)
            doc.pop("_scan_id", None)
            try:
                findings.append(Finding(**doc))
            except Exception:
                pass
        return findings

    # ─── Events ──────────────────────────────────────────────────────

    async def push_event(self, event: AgentEvent) -> None:
        # Persist to MongoDB
        doc = event.model_dump(mode="json")
        await self._events_col.insert_one(doc)

        # Also push to in-memory SSE queue for live clients
        async with self._lock:
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
        """Sync wrapper — raises. Use get_event_history_async."""
        raise RuntimeError("Use get_event_history_async() instead.")

    async def get_event_history_async(self, scan_id: str) -> List[AgentEvent]:
        events: List[AgentEvent] = []
        async for doc in self._events_col.find({"scan_id": scan_id}).sort("timestamp", 1):
            doc.pop("_id", None)
            try:
                events.append(AgentEvent(**doc))
            except Exception:
                pass
        return events

    async def close_event_queue(self, scan_id: str) -> None:
        """Signal SSE consumers that this scan is done (sentinel None)."""
        async with self._lock:
            q = self._event_queues.get(scan_id)
        if q is not None:
            await q.put(None)

    # ─── Lifecycle ───────────────────────────────────────────────────

    async def ping(self) -> bool:
        """Check MongoDB connection health."""
        try:
            await self._client.admin.command("ping")
            return True
        except Exception:
            return False

    def close(self) -> None:
        self._client.close()
