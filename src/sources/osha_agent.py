"""OSHA enforcement records agent."""

from __future__ import annotations

from typing import Any, Dict, List

from .base import BaseAgent, SourceConfig


class OshaAgent(BaseAgent):
    """Scrapes OSHA enforcement inspection and citation records."""

    def _build_goal(self, target: str, query: str) -> str:
        return f"""
        Navigate to the OSHA Enforcement Data page at {self.source.base_url}.
        Use the establishment search to find records for company: "{target}".
        The query context is: {query}

        For each inspection or citation found, extract:
        - case_id: inspection number
        - employer_name: establishment name as listed
        - violation_type: citation type (serious, willful, repeat, other-than-serious, failure-to-abate)
        - proposed_penalty: dollar amount (numeric only)
        - decision_date: date of inspection (YYYY-MM-DD if possible)
        - status: open or closed
        - jurisdiction: state name or "Federal"
        - description: brief description of the cited standard or hazard
        - source_url: URL for this specific inspection record

        Return a JSON object: {{"cases": [...]}}
        If no results are found, return {{"cases": []}}
        """

    def _normalize_result(self, raw_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        cases = raw_json.get("cases", [])
        normalized = []
        for case in cases:
            if not isinstance(case, dict):
                continue
            normalized.append({
                "case_id": case.get("case_id", ""),
                "employer_name": case.get("employer_name", ""),
                "violation_type": case.get("violation_type", "serious"),
                "proposed_penalty": case.get("proposed_penalty", 0),
                "decision_date": case.get("decision_date", ""),
                "status": (case.get("status") or "unknown").lower(),
                "jurisdiction": case.get("jurisdiction", "US Federal"),
                "description": case.get("description", ""),
                "source_url": case.get("source_url", self.source.base_url),
                "source": "OSHA",
            })
        return normalized
