"""
Risk scoring and result aggregation for AutoDiligence findings.

Normalises raw TinyFish output into a ranked list of DiligenceFindings
with severity labels derived from penalty amount, violation type keywords,
and open/closed status.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


_CRITICAL_KEYWORDS = {
    "willful", "repeat", "fraud", "criminal", "egregious",
    "reckless", "knowingly", "felony",
}
_SERIOUS_KEYWORDS = {
    "serious", "warning letter", "consent order", "cease and desist",
    "enforcement", "violation",
}
_MODERATE_KEYWORDS = {
    "moderate", "citation", "notice", "corrective",
}


def _classify_severity(violation_type: str, penalty: float, status: str) -> str:
    vt = violation_type.lower()

    if any(k in vt for k in _CRITICAL_KEYWORDS) or penalty >= 500_000:
        return "critical"
    if any(k in vt for k in _SERIOUS_KEYWORDS) or penalty >= 100_000:
        return "high"
    if any(k in vt for k in _MODERATE_KEYWORDS) or penalty >= 10_000:
        return "medium"
    return "low"


def _parse_penalty(raw: Any) -> float:
    """Parse penalty from various formats to a float USD value."""
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).replace(",", "").replace("$", "").strip().lower()
    multiplier = 1.0
    if s.endswith("m"):
        multiplier = 1_000_000
        s = s[:-1]
    elif s.endswith("k"):
        multiplier = 1_000
        s = s[:-1]
    try:
        return float(s) * multiplier
    except ValueError:
        return 0.0


@dataclass
class DiligenceFinding:
    """Normalised finding across all sources."""
    finding_id: str
    source_id: str
    case_id: str
    case_type: str
    entity_name: str
    violation_type: str
    decision_date: str
    penalty_amount: float
    severity: str          # critical | high | medium | low
    status: str            # open | settled | closed | appealed
    description: str
    source_url: str
    jurisdiction: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "source_id": self.source_id,
            "case_id": self.case_id,
            "case_type": self.case_type,
            "entity_name": self.entity_name,
            "violation_type": self.violation_type,
            "decision_date": self.decision_date,
            "penalty_amount": self.penalty_amount,
            "severity": self.severity,
            "status": self.status,
            "description": self.description,
            "source_url": self.source_url,
            "jurisdiction": self.jurisdiction,
        }


class ResultAggregator:
    """Consolidates raw TinyFish results into normalised DiligenceFindings."""

    _SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    @staticmethod
    def normalize(source_id: str, raw_result: Dict[str, Any]) -> List[DiligenceFinding]:
        """
        Convert a raw agent result dict into a list of DiligenceFindings.
        Expected input shape: {"cases": [...], "status": "success"}
        """
        findings: List[DiligenceFinding] = []
        cases = raw_result.get("cases", [])
        if not isinstance(cases, list):
            return findings

        for i, case in enumerate(cases):
            if not isinstance(case, dict):
                continue

            penalty = _parse_penalty(case.get("proposed_penalty") or case.get("penalty_amount"))
            violation_type = case.get("violation_type") or case.get("case_type") or "unknown"
            status = (case.get("status") or "unknown").lower()
            severity = _classify_severity(violation_type, penalty, status)

            finding = DiligenceFinding(
                finding_id=f"{source_id}_{case.get('case_id', i)}",
                source_id=source_id,
                case_id=str(case.get("case_id") or f"unk-{i}"),
                case_type=source_id,
                entity_name=str(case.get("employer_name") or case.get("entity_name") or ""),
                violation_type=violation_type,
                decision_date=str(case.get("decision_date") or ""),
                penalty_amount=penalty,
                severity=severity,
                status=status,
                description=str(case.get("description") or ""),
                source_url=str(case.get("source_url") or ""),
                jurisdiction=str(case.get("jurisdiction") or ""),
                raw=case,
            )
            findings.append(finding)

        return findings

    @classmethod
    def aggregate_all(
        cls,
        raw_results: Dict[str, Dict[str, Any]],
    ) -> List[DiligenceFinding]:
        """Merge results across sources, sorted by severity then penalty."""
        all_findings: List[DiligenceFinding] = []
        for source_id, result in raw_results.items():
            if result.get("status") in ("completed", "success"):
                all_findings.extend(cls.normalize(source_id, result))

        all_findings.sort(
            key=lambda f: (
                cls._SEVERITY_ORDER.get(f.severity, 99),
                -f.penalty_amount,
            )
        )
        return all_findings

    @staticmethod
    def compute_risk_score(findings: List[DiligenceFinding]) -> Dict[str, Any]:
        """
        Compute an aggregate risk score 0-100 from findings.
        Higher = more risk.
        """
        if not findings:
            return {"score": 0, "label": "Clean", "breakdown": {}}

        weights = {"critical": 30, "high": 15, "medium": 5, "low": 1}
        open_mult = 1.5  # open cases are worth 50% more

        raw_score = 0.0
        breakdown: Dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}

        for f in findings:
            mult = open_mult if f.status == "open" else 1.0
            raw_score += weights.get(f.severity, 0) * mult
            breakdown[f.severity] = breakdown.get(f.severity, 0) + 1

        # Clamp to 0-100
        score = min(100, int(raw_score))

        if score >= 70:
            label = "Critical Risk"
        elif score >= 40:
            label = "High Risk"
        elif score >= 15:
            label = "Medium Risk"
        elif score > 0:
            label = "Low Risk"
        else:
            label = "Clean"

        return {"score": score, "label": label, "breakdown": breakdown}
