"""
/api/analytics — Cross-scan analytics: risk trends, full-text search, benchmarks.
"""

from __future__ import annotations

from collections import Counter
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..store import scan_store

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ------------------------------------------------------------------ risk trend

@router.get("/risk-trend")
async def risk_trend(
    target: str = Query(..., description="Entity name to compute trend for"),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    """
    Return chronological risk score history for a target entity.
    Useful for detecting improvement/deterioration over time.
    """
    all_scans = await scan_store.list_all()
    matching = [
        s for s in all_scans
        if s.target.lower() == target.lower() and s.status == "completed"
    ]
    if not matching:
        raise HTTPException(status_code=404, detail=f"No completed scans found for '{target}'")

    matching.sort(key=lambda s: s.created_at)
    series = matching[-limit:]

    data_points = [
        {
            "scan_id": s.scan_id,
            "date": s.created_at.isoformat(),
            "risk_score": s.risk_score,
            "risk_label": s.risk_label,
            "findings_count": s.findings_count,
            "sources_queried": s.sources_total,
        }
        for s in series
    ]

    scores = [s.risk_score or 0 for s in series]
    delta = (scores[-1] - scores[0]) if len(scores) >= 2 else 0
    trend_dir = "improving" if delta < -5 else "worsening" if delta > 5 else "stable"

    return {
        "target": target,
        "total_scans": len(matching),
        "shown": len(series),
        "trend": trend_dir,
        "delta_risk": delta,
        "current_risk_score": scores[-1] if scores else None,
        "data_points": data_points,
    }


# ------------------------------------------------------------------ full-text search

@router.get("/search")
async def search_findings(
    q: str = Query(..., min_length=2, description="Search term (matches description, violation_type, case_id, entity_name)"),
    scan_id: Optional[str] = Query(default=None, description="Limit search to a specific scan"),
    severity: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    """
    Full-text search across finding descriptions, violation types, and case IDs.
    Optionally scoped to a single scan.
    """
    term = q.lower()

    if scan_id:
        scan = await scan_store.get(scan_id)
        if scan is None:
            raise HTTPException(status_code=404, detail="Scan not found")
        all_findings = await scan_store.get_findings_async(scan_id)
    else:
        # Search across all completed scans (expensive — capped)
        all_scans = await scan_store.list_all()
        completed = [s for s in all_scans if s.status == "completed"]
        all_findings = []
        for s in completed[:20]:  # cap at 20 scans
            all_findings.extend(await scan_store.get_findings_async(s.scan_id))

    # Filter by term
    results = [
        f for f in all_findings
        if (
            term in (f.description or "").lower()
            or term in (f.violation_type or "").lower()
            or term in (f.case_id or "").lower()
            or term in (f.entity_name or "").lower()
            or term in (f.jurisdiction or "").lower()
        )
    ]

    if severity:
        results = [f for f in results if f.severity == severity]

    results.sort(key=lambda f: ["critical", "high", "medium", "low"].index(f.severity)
                 if f.severity in ("critical", "high", "medium", "low") else 9)

    return {
        "query": q,
        "total": len(results),
        "shown": min(len(results), limit),
        "results": [f.model_dump() for f in results[:limit]],
    }


# ------------------------------------------------------------------ portfolio overview

@router.get("/portfolio")
async def portfolio_overview() -> dict:
    """
    Aggregate stats across ALL completed scans.
    Great for a portfolio/watchlist-level executive view.
    """
    all_scans = await scan_store.list_all()
    completed = [s for s in all_scans if s.status == "completed"]

    if not completed:
        return {
            "total_scans": 0,
            "total_findings": 0,
            "total_exposure": 0,
            "avg_risk_score": None,
            "entities_at_risk": [],
            "by_severity": {},
            "by_source": {},
        }

    # Gather all findings
    all_findings = []
    for s in completed:
        findings = await scan_store.get_findings_async(s.scan_id)
        all_findings.extend(findings)

    total_exposure = sum(f.penalty_amount for f in all_findings)
    avg_risk = round(
        sum(s.risk_score or 0 for s in completed) / len(completed), 1
    )

    sev_counts = dict(Counter(f.severity for f in all_findings))
    source_counts = dict(Counter(f.source_id for f in all_findings))

    # Entities sorted by risk score
    entities_at_risk = sorted(
        [
            {
                "target": s.target,
                "scan_id": s.scan_id,
                "risk_score": s.risk_score,
                "risk_label": s.risk_label,
                "findings_count": s.findings_count,
                "last_scanned": s.created_at.isoformat(),
            }
            for s in completed
        ],
        key=lambda e: e["risk_score"] or 0,
        reverse=True,
    )[:10]

    return {
        "total_scans": len(completed),
        "total_findings": len(all_findings),
        "total_exposure": total_exposure,
        "avg_risk_score": avg_risk,
        "entities_at_risk": entities_at_risk,
        "by_severity": sev_counts,
        "by_source": source_counts,
    }


# ------------------------------------------------------------------ benchmark

@router.get("/benchmark")
async def benchmark_target(
    target: str = Query(..., description="Entity to benchmark against all scanned entities"),
) -> dict:
    """
    Compare a target's risk score against the average across all completed scans.
    """
    all_scans = await scan_store.list_all()
    completed = [s for s in all_scans if s.status == "completed"]

    if not completed:
        raise HTTPException(status_code=404, detail="No completed scans available for benchmarking")

    target_scans = [
        s for s in completed
        if s.target.lower() == target.lower()
    ]
    if not target_scans:
        raise HTTPException(status_code=404, detail=f"No completed scans found for '{target}'")

    latest = max(target_scans, key=lambda s: s.created_at)
    all_scores = [s.risk_score or 0 for s in completed]
    avg_all = round(sum(all_scores) / len(all_scores), 1)
    percentile = round(
        sum(1 for x in all_scores if x <= (latest.risk_score or 0)) / len(all_scores) * 100
    )

    return {
        "target": target,
        "risk_score": latest.risk_score,
        "risk_label": latest.risk_label,
        "avg_all_entities": avg_all,
        "percentile": percentile,
        "better_than_pct": 100 - percentile,
        "total_entities_compared": len({s.target for s in completed}),
        "interpretation": (
            "Above average risk" if (latest.risk_score or 0) > avg_all
            else "Below average risk"
        ),
    }
