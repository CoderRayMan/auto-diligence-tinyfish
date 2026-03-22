"""FDA enforcement and warning letters agent."""

from __future__ import annotations

from typing import Any, Dict, List

from .base import BaseAgent, SourceConfig


class FdaAgent(BaseAgent):
    """Scrapes FDA warning letters and enforcement actions."""

    def _build_goal(self, target: str, query: str) -> str:
        return f"""
        Navigate to the FDA warning letters page at {self.source.base_url}.
        Search for warning letters and enforcement actions issued to company: "{target}".
        The query context is: {query}

        For each enforcement action or warning letter found, extract:
        - case_id: FDA letter or reference number
        - employer_name: company or individual named
        - violation_type: FDA violation category (e.g., GMP, labeling, adulteration, CGMP, 510k)
        - proposed_penalty: any monetary penalty mentioned (0 if none)
        - decision_date: date the letter or action was issued (YYYY-MM-DD)
        - status: open or closed
        - jurisdiction: "US Federal"
        - description: summary of violations cited
        - source_url: direct URL to the warning letter or press release

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
                "violation_type": case.get("violation_type", "FDA Violation"),
                "proposed_penalty": case.get("proposed_penalty", 0),
                "decision_date": case.get("decision_date", ""),
                "status": (case.get("status") or "unknown").lower(),
                "jurisdiction": "US Federal",
                "description": case.get("description", ""),
                "source_url": case.get("source_url", self.source.base_url),
                "source": "FDA",
            })
        return normalized
