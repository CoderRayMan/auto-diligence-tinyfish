"""
/api/findings — Query normalised findings for a completed scan.

Includes CSV export, executive summary, comparison, and per-scan statistics.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..schemas import Finding, FindingsPage, get_persona
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


# ------------------------------------------------------------------ CSV export

_CSV_COLUMNS = [
    "finding_id", "source_id", "case_id", "entity_name", "violation_type",
    "severity", "status", "penalty_amount", "decision_date", "jurisdiction",
    "description", "source_url",
]


@router.get("/export/csv")
async def export_findings_csv(
    scan_id: str = Query(..., description="Scan ID to export findings for"),
) -> StreamingResponse:
    """Download all findings for a scan as a CSV file."""
    scan = await scan_store.get(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    findings = scan_store.get_findings(scan_id)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for f in findings:
        writer.writerow(f.model_dump())

    buf.seek(0)
    filename = f"autodiligence_{scan.target.replace(' ', '_')}_{scan_id[:8]}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# -------------------------------------------------------------- statistics

@router.get("/stats/summary")
async def findings_stats(
    scan_id: str = Query(..., description="Scan ID"),
) -> dict:
    """
    Return aggregate statistics for a scan's findings.
    Great for dashboards and executive reports.
    """
    scan = await scan_store.get(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    findings = scan_store.get_findings(scan_id)
    if not findings:
        return {
            "scan_id": scan_id,
            "target": scan.target,
            "total_findings": 0,
            "by_severity": {},
            "by_source": {},
            "by_status": {},
            "total_exposure": 0,
            "top_violations": [],
        }

    sev_counts = Counter(f.severity for f in findings)
    source_counts = Counter(f.source_id for f in findings)
    status_counts = Counter(f.status for f in findings)
    total_exposure = sum(f.penalty_amount for f in findings)

    # Top violation types by frequency
    vtype_counts = Counter(f.violation_type for f in findings)
    top_violations = [
        {"type": vt, "count": c}
        for vt, c in vtype_counts.most_common(10)
    ]

    # Highest individual penalties
    top_penalties = sorted(findings, key=lambda f: f.penalty_amount, reverse=True)[:5]

    return {
        "scan_id": scan_id,
        "target": scan.target,
        "persona_id": scan.persona_id,
        "total_findings": len(findings),
        "by_severity": dict(sev_counts),
        "by_source": dict(source_counts),
        "by_status": dict(status_counts),
        "total_exposure": total_exposure,
        "top_violations": top_violations,
        "top_penalties": [
            {
                "case_id": f.case_id,
                "source_id": f.source_id,
                "penalty_amount": f.penalty_amount,
                "violation_type": f.violation_type,
                "severity": f.severity,
            }
            for f in top_penalties
        ],
        "risk_score": scan.risk_score,
        "risk_label": scan.risk_label,
    }


# --------------------------------------------------------- executive report

def _fmt_currency(amount: float) -> str:
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    if amount >= 1_000:
        return f"${amount / 1_000:.0f}k"
    if amount > 0:
        return f"${amount:,.0f}"
    return "$0"


@router.get("/report/executive")
async def executive_report(
    scan_id: str = Query(..., description="Scan ID"),
) -> dict:
    """
    Generate a structured executive-ready diligence report.
    Returns sections that can be rendered as rich text or copied into a document.
    """
    scan = await scan_store.get(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    findings = scan_store.get_findings(scan_id)
    persona = get_persona(scan.persona_id) if scan.persona_id else None

    sev_counts = Counter(f.severity for f in findings)
    source_counts = Counter(f.source_id for f in findings)
    total_exposure = sum(f.penalty_amount for f in findings)
    open_cases = [f for f in findings if f.status == "open"]
    critical_findings = [f for f in findings if f.severity == "critical"]

    # Build the report sections
    title = f"Regulatory Due Diligence Report — {scan.target}"
    subtitle = f"Generated {datetime.utcnow().strftime('%B %d, %Y')} via AutoDiligence"
    if persona:
        subtitle += f" | Perspective: {persona.label}"

    # Executive summary paragraph
    if not findings:
        exec_summary = (
            f"A comprehensive regulatory sweep of {scan.sources_total} federal data sources "
            f"returned no enforcement actions, violations, or regulatory warnings for {scan.target}. "
            f"This entity appears clean from a regulatory compliance standpoint."
        )
    else:
        exec_summary = (
            f"A sweep of {scan.sources_total} federal regulatory data sources identified "
            f"{len(findings)} enforcement action(s) against {scan.target} with a combined "
            f"financial exposure of {_fmt_currency(total_exposure)}. "
            f"The overall risk score is {scan.risk_score}/100 ({scan.risk_label}). "
        )
        if critical_findings:
            exec_summary += (
                f"{len(critical_findings)} critical finding(s) require immediate attention. "
            )
        if open_cases:
            exec_summary += (
                f"{len(open_cases)} case(s) remain open or unresolved."
            )

    # Key metrics
    key_metrics = {
        "risk_score": scan.risk_score,
        "risk_label": scan.risk_label,
        "total_findings": len(findings),
        "total_exposure": total_exposure,
        "total_exposure_formatted": _fmt_currency(total_exposure),
        "critical_count": sev_counts.get("critical", 0),
        "high_count": sev_counts.get("high", 0),
        "medium_count": sev_counts.get("medium", 0),
        "low_count": sev_counts.get("low", 0),
        "open_cases": len(open_cases),
        "sources_queried": scan.sources_total,
        "sources_with_results": len(source_counts),
    }

    # Critical items
    critical_items = [
        {
            "case_id": f.case_id,
            "source": f.source_id,
            "violation": f.violation_type,
            "penalty": _fmt_currency(f.penalty_amount),
            "status": f.status,
            "description": f.description,
            "source_url": f.source_url,
        }
        for f in critical_findings[:10]
    ]

    # Source breakdown
    source_breakdown = []
    for src_id, count in source_counts.most_common():
        src_findings = [f for f in findings if f.source_id == src_id]
        src_exposure = sum(f.penalty_amount for f in src_findings)
        source_breakdown.append({
            "source_id": src_id,
            "findings_count": count,
            "exposure": _fmt_currency(src_exposure),
            "severities": dict(Counter(f.severity for f in src_findings)),
        })

    # Recommendations
    recommendations = []
    if critical_findings:
        recommendations.append(
            "URGENT: Review critical findings immediately — these represent material risk factors."
        )
    if open_cases:
        recommendations.append(
            f"Track {len(open_cases)} open case(s) — pending outcomes may affect future liability."
        )
    if sev_counts.get("high", 0) > 3:
        recommendations.append(
            "Pattern of high-severity violations detected — consider enhanced compliance monitoring."
        )
    if total_exposure > 1_000_000:
        recommendations.append(
            f"Total financial exposure exceeds $1M ({_fmt_currency(total_exposure)}) — factor into valuation."
        )
    if not findings:
        recommendations.append("No adverse findings — entity passes initial regulatory screening.")

    return {
        "title": title,
        "subtitle": subtitle,
        "scan_id": scan_id,
        "target": scan.target,
        "generated_at": datetime.utcnow().isoformat(),
        "persona": persona.label if persona else None,
        "executive_summary": exec_summary,
        "key_metrics": key_metrics,
        "critical_items": critical_items,
        "source_breakdown": source_breakdown,
        "recommendations": recommendations,
    }


# ----------------------------------------------------------- scan comparison

@router.get("/compare")
async def compare_scans(
    scan_a: str = Query(..., description="First scan ID"),
    scan_b: str = Query(..., description="Second scan ID"),
) -> dict:
    """
    Compare findings from two scans.
    Useful for before/after analysis or comparing two targets.
    """
    sa = await scan_store.get(scan_a)
    sb = await scan_store.get(scan_b)
    if sa is None or sb is None:
        raise HTTPException(status_code=404, detail="One or both scans not found")

    fa = scan_store.get_findings(scan_a)
    fb = scan_store.get_findings(scan_b)

    def _summarize(scan, findings):
        sev = Counter(f.severity for f in findings)
        return {
            "scan_id": scan.scan_id,
            "target": scan.target,
            "risk_score": scan.risk_score,
            "risk_label": scan.risk_label,
            "total_findings": len(findings),
            "total_exposure": sum(f.penalty_amount for f in findings),
            "by_severity": dict(sev),
            "sources_queried": scan.sources_total,
        }

    # Find case IDs that overlap
    case_ids_a = {f.case_id for f in fa}
    case_ids_b = {f.case_id for f in fb}
    shared = case_ids_a & case_ids_b
    only_a = case_ids_a - case_ids_b
    only_b = case_ids_b - case_ids_a

    return {
        "scan_a": _summarize(sa, fa),
        "scan_b": _summarize(sb, fb),
        "shared_case_ids": len(shared),
        "unique_to_a": len(only_a),
        "unique_to_b": len(only_b),
        "delta_risk": (sa.risk_score or 0) - (sb.risk_score or 0),
        "delta_findings": len(fa) - len(fb),
        "delta_exposure": sum(f.penalty_amount for f in fa) - sum(f.penalty_amount for f in fb),
    }
