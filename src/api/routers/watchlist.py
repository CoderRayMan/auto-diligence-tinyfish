"""
/api/watchlist — Pin entities for ongoing monitoring.

Tracks scanned entities and surfaces staleness so analysts
can re-run diligence on a schedule.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..store import scan_store

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

# In-memory watchlist (persists in process; simple for demo purposes)
# Structure: { entity_name: WatchlistEntry }
_WATCHLIST: dict[str, "WatchlistEntry"] = {}
_LOCK = asyncio.Lock()

STALE_AFTER_DAYS = 7  # mark as stale if last scan > 7 days ago


class WatchlistEntry(BaseModel):
    entity_name: str
    added_at: str
    last_scan_id: Optional[str] = None
    last_scan_at: Optional[str] = None
    last_risk_score: Optional[int] = None
    last_risk_label: Optional[str] = None
    is_stale: bool = False
    persona_id: Optional[str] = None
    notes: Optional[str] = None


class AddToWatchlistRequest(BaseModel):
    entity_name: str
    persona_id: Optional[str] = None
    notes: Optional[str] = None


def _compute_staleness(entry: WatchlistEntry) -> bool:
    if not entry.last_scan_at:
        return True
    try:
        last = datetime.fromisoformat(entry.last_scan_at.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - last) > timedelta(days=STALE_AFTER_DAYS)
    except Exception:
        return True


async def _refresh_entry(entry: WatchlistEntry) -> WatchlistEntry:
    """Pull latest completed scan for this entity from the store."""
    all_scans = await scan_store.list_all()
    matching = [
        s for s in all_scans
        if s.target.lower() == entry.entity_name.lower() and s.status == "completed"
    ]
    if matching:
        latest = max(matching, key=lambda s: s.created_at)
        entry.last_scan_id = latest.scan_id
        entry.last_scan_at = latest.completed_at.isoformat() if latest.completed_at else None
        entry.last_risk_score = latest.risk_score
        entry.last_risk_label = latest.risk_label
    entry.is_stale = _compute_staleness(entry)
    return entry


# ------------------------------------------------------------------ routes

@router.get("", response_model=List[WatchlistEntry])
async def list_watchlist() -> List[WatchlistEntry]:
    """Return all watched entities with staleness info."""
    async with _LOCK:
        entries = list(_WATCHLIST.values())

    # Refresh staleness from latest scans
    refreshed = []
    for entry in entries:
        refreshed.append(await _refresh_entry(entry))

    return sorted(refreshed, key=lambda e: e.entity_name)


@router.post("", response_model=WatchlistEntry, status_code=201)
async def add_to_watchlist(req: AddToWatchlistRequest) -> WatchlistEntry:
    """Add an entity to the watchlist."""
    name = req.entity_name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="entity_name cannot be empty")

    async with _LOCK:
        if name.lower() in {k.lower() for k in _WATCHLIST}:
            raise HTTPException(status_code=409, detail="Entity already in watchlist")

        entry = WatchlistEntry(
            entity_name=name,
            added_at=datetime.now(timezone.utc).isoformat(),
            persona_id=req.persona_id,
            notes=req.notes,
        )
        _WATCHLIST[name] = entry

    return await _refresh_entry(entry)


@router.delete("/{entity_name}", status_code=204)
async def remove_from_watchlist(entity_name: str) -> None:
    """Remove an entity from the watchlist."""
    async with _LOCK:
        key = next((k for k in _WATCHLIST if k.lower() == entity_name.lower()), None)
        if key is None:
            raise HTTPException(status_code=404, detail="Entity not in watchlist")
        del _WATCHLIST[key]


@router.get("/stale", response_model=List[WatchlistEntry])
async def get_stale_entries() -> List[WatchlistEntry]:
    """Return watchlist entities that need re-scanning (stale > 7 days)."""
    all_entries = await list_watchlist()
    return [e for e in all_entries if e.is_stale]


@router.post("/{entity_name}/refresh", response_model=WatchlistEntry)
async def refresh_watchlist_entry(entity_name: str) -> WatchlistEntry:
    """Refresh the staleness state of a specific watchlist entry."""
    async with _LOCK:
        key = next((k for k in _WATCHLIST if k.lower() == entity_name.lower()), None)
        if key is None:
            raise HTTPException(status_code=404, detail="Entity not in watchlist")
        entry = _WATCHLIST[key]

    return await _refresh_entry(entry)
