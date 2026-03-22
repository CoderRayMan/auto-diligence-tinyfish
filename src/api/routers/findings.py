"""
/api/findings — Query normalised findings for a completed scan.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..schemas import Finding, FindingsPage
from ..store import scan_store

router = APIRouter(prefix="/findings", tags=["findings"])


@router.get("", response_model=FindingsPage)
async def list_findings(
    scan_id: str = Query(..., description="Scan ID to fetch findings for"),
    severity: Optional[str] = Query(default=None, description="Filter by severity: critical|high|medium|low"),
    status: Optional[str] = Query(default=None, description="Filter by status: open|settled|closed|appealed"),
    source_id: Optional[str] = Query(default=None, description="Filter by source ID"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> FindingsPage:
    """Return paginated, filterable findings for a given scan."""
    scan = await scan_store.get(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    findings: List[Finding] = scan_store.get_findings(scan_id)

    # Apply filters
    if severity:
        findings = [f for f in findings if f.severity == severity]
    if status:
        findings = [f for f in findings if f.status == status]
    if source_id:
        findings = [f for f in findings if f.source_id == source_id]

    total = len(findings)
    start = (page - 1) * page_size
    page_findings = findings[start : start + page_size]

    return FindingsPage(
        scan_id=scan_id,
        total=total,
        page=page,
        page_size=page_size,
        findings=page_findings,
    )


@router.get("/{finding_id}", response_model=Finding)
async def get_finding(finding_id: str, scan_id: str = Query(...)) -> Finding:
    """Get a single finding by ID."""
    findings = scan_store.get_findings(scan_id)
    for f in findings:
        if f.finding_id == finding_id:
            return f
    raise HTTPException(status_code=404, detail="Finding not found")
