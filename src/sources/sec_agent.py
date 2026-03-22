"""SEC enforcement actions agent."""

from __future__ import annotations

from typing import Any, Dict, List

from .base import BaseAgent, SourceConfig


class SecAgent(BaseAgent):
    """Scrapes SEC enforcement actions, litigation releases, and orders."""

    def _build_goal(self, target: str, query: str) -> str:
        return f"""
        Navigate to the SEC enforcement actions page at {self.source.base_url}.
        Search for SEC enforcement actions, litigation releases, and administrative orders
        involving company or individual: "{target}".
        The query context is: {query}

        For each enforcement action found, extract:
        - case_id: SEC release number or litigation release number
        - employer_name: company or individual named in the action
        - violation_type: type of securities violation (e.g., fraud, disclosure failure,
          insider trading, market manipulation, accounting fraud)
        - proposed_penalty: disgorgement or civil penalty amount (numeric, 0 if none)
        - decision_date: date the action was announced (YYYY-MM-DD)
        - status: settled | litigated | ongoing | closed
        - jurisdiction: "US Federal (SEC)"
        - description: brief summary of the alleged violations
        - source_url: URL to the SEC press release, order, or complaint

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
                "violation_type": case.get("violation_type", "Securities Violation"),
                "proposed_penalty": case.get("proposed_penalty", 0),
                "decision_date": case.get("decision_date", ""),
                "status": (case.get("status") or "unknown").lower(),
                "jurisdiction": "US Federal (SEC)",
                "description": case.get("description", ""),
                "source_url": case.get("source_url", self.source.base_url),
                "source": "SEC",
            })
        return normalized
