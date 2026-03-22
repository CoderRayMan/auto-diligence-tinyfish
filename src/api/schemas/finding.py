from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class FindingStatus(str, Enum):
    open = "open"
    settled = "settled"
    closed = "closed"
    appealed = "appealed"
    unknown = "unknown"


class Finding(BaseModel):
    finding_id: str
    scan_id: str
    source_id: str
    case_id: str
    case_type: str
    entity_name: str
    violation_type: str
    decision_date: str
    penalty_amount: float
    severity: Severity
    status: FindingStatus
    description: str
    source_url: str
    jurisdiction: str

    class Config:
        use_enum_values = True


class FindingsPage(BaseModel):
    scan_id: str
    total: int
    page: int
    page_size: int
    findings: list[Finding]
