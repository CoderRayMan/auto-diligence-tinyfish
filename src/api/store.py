"""
MongoDB-backed scan store.

Scans and findings are persisted to MongoDB Atlas so data survives
server restarts. SSE event queues remain in-memory (live-only).
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from .schemas import ScanResponse, ScanStatus, Finding, AgentEvent

logger = logging.getLogger(__name__)


def _serialize_value(v: Any) -> Any:
    """Recursively prepare a Python value for MongoDB storage."""
    if isinstance(v, datetime):
        return v.isoformat()
    if hasattr(v, "value"):          # StrEnum / Enum
        return v.value
    if hasattr(v, "model_dump"):     # Pydantic model
        return {k: _serialize_value(vv) for k, vv in v.model_dump(mode="json").items()}
    if isinstance(v, list):
        return [_serialize_value(i) for i in v]
    if isinstance(v, dict):
        return {k: _serialize_value(vv) for k, vv in v.items()}
    return v


def _doc_to_scan(doc: dict) -> ScanResponse:
    """Convert a raw MongoDB doc back to ScanResponse."""
    doc = dict(doc)
    doc["scan_id"] = doc.pop("_id", doc.get("scan_id", ""))
    return ScanResponse(**doc)


def _doc_to_finding(doc: dict) -> Finding:
    """Convert a raw MongoDB doc back to Finding."""
    doc = dict(doc)
    doc["finding_id"] = doc.pop("_id", doc.get("finding_id", ""))
    return Finding(**doc)


class ScanStore:
    """
    Async scan store backed by MongoDB Atlas.

    Drop-in replacement for the old in-memory ScanStore — all public
    method signatures are identical, except `get_findings` is now async.
    The SSE event queues are still in-memory (events are live-only).
    """

    def __init__(self) -> None:
        self._event_queues: Dict[str, asyncio.Queue] = {}
        self._event_history: Dict[str, List[AgentEvent]] = {}
        self._lock = asyncio.Lock()
        self._client = None
        self._db = None

    # ---------------------------------------------------------- lifecycle

    async def connect(self) -> None:
        """Connect to MongoDB using MONGODB_URI from .env.

        Raises RuntimeError if the connection cannot be established so that
        the FastAPI lifespan fails immediately rather than running without DB.
        """
        uri = os.getenv("MONGODB_URI", "").strip()
        db_name = os.getenv("MONGODB_DB", "autodiligence")
        if not uri:
            raise RuntimeError("MONGODB_URI is not set — cannot start without a database")
        try:
            from pymongo import MongoClient
            from pymongo.server_api import ServerApi

            def _connect_sync():
                c = MongoClient(uri, server_api=ServerApi("1"), serverSelectionTimeoutMS=30000)
                c.admin.command("ping")
                db = c[db_name]
                db.scans.create_index("created_at")
                db.findings.create_index("scan_id")
                return c, db

            self._client, self._db = await asyncio.to_thread(_connect_sync)
            logger.info(f"Connected to MongoDB — db={db_name}")
        except Exception as exc:
            self._client = None
            self._db = None
            raise RuntimeError(f"MongoDB connection failed: {exc}") from exc

    async def disconnect(self) -> None:
        """Close MongoDB connection. Called from FastAPI lifespan shutdown."""
        if self._client is not None:
            await asyncio.to_thread(self._client.close)
            logger.info("MongoDB connection closed")

    @property
    def _mongo_available(self) -> bool:
        return self._db is not None

    async def _ensure_connected(self) -> None:
        """Lazily (re)connect to MongoDB if not already connected."""
        if self._db is None:
            await self.connect()

    # ---------------------------------------------------------------- scans

    # ---- sync helpers (run via asyncio.to_thread) ---------------------------

    def _sync_insert_scan(self, doc: dict) -> None:
        self._db.scans.insert_one(doc)

    def _sync_find_scan(self, scan_id: str) -> Optional[dict]:
        return self._db.scans.find_one({"_id": scan_id})

    def _sync_list_scans(self) -> List[dict]:
        return list(self._db.scans.find({}).sort("created_at", -1))

    def _sync_update_scan(self, scan_id: str, updates: dict) -> None:
        self._db.scans.update_one({"_id": scan_id}, {"$set": updates})

    def _sync_replace_findings(self, scan_id: str, docs: List[dict]) -> None:
        self._db.findings.delete_many({"scan_id": scan_id})
        if docs:
            self._db.findings.insert_many(docs)

    def _sync_find_findings(self, scan_id: str) -> List[dict]:
        return list(self._db.findings.find({"scan_id": scan_id}))

    # ---- async public API ---------------------------------------------------

    async def create(self, scan: ScanResponse) -> None:
        async with self._lock:
            self._event_queues[scan.scan_id] = asyncio.Queue(maxsize=500)
            self._event_history[scan.scan_id] = []

        if self._mongo_available:
            doc = {k: _serialize_value(v) for k, v in scan.model_dump(mode="json").items()}
            doc["_id"] = doc.pop("scan_id")
            try:
                await asyncio.to_thread(self._sync_insert_scan, doc)
            except Exception as exc:
                logger.error(f"MongoDB create scan failed: {exc}")

    async def get(self, scan_id: str) -> Optional[ScanResponse]:
        await self._ensure_connected()
        if self._mongo_available:
            try:
                doc = await asyncio.to_thread(self._sync_find_scan, scan_id)
                if doc is not None:
                    return _doc_to_scan(doc)
            except Exception as exc:
                logger.error(f"MongoDB get scan failed: {exc}")
        return None

    async def list_all(self) -> List[ScanResponse]:
        await self._ensure_connected()
        if not self._mongo_available:
            return []
        scans: List[ScanResponse] = []
        try:
            docs = await asyncio.to_thread(self._sync_list_scans)
            for doc in docs:
                try:
                    scans.append(_doc_to_scan(doc))
                except Exception as exc:
                    logger.debug(f"Skipping malformed scan doc: {exc}")
        except Exception as exc:
            logger.error(f"MongoDB list_all failed: {exc}")
        return scans

    async def update(self, scan_id: str, **kwargs: Any) -> Optional[ScanResponse]:
        updates = {k: _serialize_value(v) for k, v in kwargs.items()}
        if self._mongo_available:
            try:
                await asyncio.to_thread(self._sync_update_scan, scan_id, updates)
            except Exception as exc:
                logger.error(f"MongoDB update scan failed: {exc}")
        return await self.get(scan_id)

    # --------------------------------------------------------------- findings

    async def add_findings(self, scan_id: str, findings: List[Finding]) -> None:
        if not findings or not self._mongo_available:
            return
        docs = []
        for f in findings:
            doc = {k: _serialize_value(v) for k, v in f.model_dump(mode="json").items()}
            doc["_id"] = doc.pop("finding_id")
            docs.append(doc)
        try:
            await asyncio.to_thread(self._sync_replace_findings, scan_id, docs)
        except Exception as exc:
            logger.error(f"MongoDB add_findings failed: {exc}")

    async def get_findings(self, scan_id: str) -> List[Finding]:
        await self._ensure_connected()
        if not self._mongo_available:
            return []
        findings: List[Finding] = []
        try:
            docs = await asyncio.to_thread(self._sync_find_findings, scan_id)
            for doc in docs:
                try:
                    findings.append(_doc_to_finding(doc))
                except Exception as exc:
                    logger.debug(f"Skipping malformed finding doc: {exc}")
        except Exception as exc:
            logger.error(f"MongoDB get_findings failed: {exc}")
        return findings

    # ---------------------------------------------------------------- events (in-memory only)

    async def push_event(self, event: AgentEvent) -> None:
        async with self._lock:
            if event.scan_id not in self._event_history:
                self._event_history[event.scan_id] = []
            self._event_history[event.scan_id].append(event)

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

    async def get_findings_async(self, scan_id: str) -> List[Finding]:
        """Async alias for get_findings — for compatibility with routers expecting this method."""
        return await self.get_findings(scan_id)

    async def close_event_queue(self, scan_id: str) -> None:
        q = self._event_queues.get(scan_id)
        if q is not None:
            await q.put(None)


# Application-wide singleton
scan_store = ScanStore()
