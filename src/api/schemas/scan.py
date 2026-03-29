from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ScanStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ScanRequest(BaseModel):
    target: str = Field(..., min_length=2, max_length=500, description="Entity to research")
    query: str = Field(
        default="regulatory violations and enforcement actions",
        max_length=2000,
        description="Research query context",
    )
    sources: Optional[List[str]] = Field(
        default=None,
        description="Specific source IDs to query. Defaults to all configured sources.",
    )
    persona_id: Optional[str] = Field(
        default=None,
        description="Persona ID to apply. Overrides sources/query with persona defaults if set.",
    )
    jurisdictions: Optional[List[str]] = Field(default=None)
    date_from: Optional[str] = Field(default=None, description="ISO date filter start")
    date_to: Optional[str] = Field(default=None, description="ISO date filter end")
    max_concurrent_agents: int = Field(default=5, ge=1, le=20)


class SourceResult(BaseModel):
    source_id: str
    status: str
    records_found: int
    execution_time_s: float
    error: Optional[str] = None


class ScanResponse(BaseModel):
    scan_id: str
    status: ScanStatus
    target: str
    query: str = "regulatory violations and enforcement actions"
    persona_id: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    sources_total: int
    sources_completed: int
    sources_failed: int
    risk_score: Optional[int] = None
    risk_label: Optional[str] = None
    findings_count: int = 0
    source_results: List[SourceResult] = []

    class Config:
        use_enum_values = True
