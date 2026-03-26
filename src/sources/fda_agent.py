"""FDA enforcement and warning letters agent."""

from __future__ import annotations

from typing import Any, Dict, List

from .base import BaseAgent, SourceConfig


def _find_cases(raw_json: Dict[str, Any]) -> List[Any]:
    """Locate the list of case records regardless of the key TinyFish used."""
    if "cases" in raw_json and isinstance(raw_json["cases"], list):
        return raw_json["cases"]
    for key in ("warning_letters", "letters", "actions", "data", "results",
                "records", "items", "violations", "findings", "enforcement_actions"):
        if key in raw_json and isinstance(raw_json[key], list):
            return raw_json[key]
    for val in raw_json.values():
        if isinstance(val, list):
            return val
    return []


class FdaAgent(BaseAgent):
    """Scrapes FDA warning letters and enforcement actions."""

    def _build_goal(self, target: str, query: str) -> str:
        return f"""
        Navigate to {self.source.base_url} and search for warning letters issued to "{target}".
        Do NOT open individual warning letter links. Extract only from the search results list.

        For each item visible in the results list, extract:
        - case_id: FDA reference or letter number
        - employer_name: company or firm name
        - violation_type: violation type or product category
        - proposed_penalty: 0
        - decision_date: issue date (YYYY-MM-DD)
        - status: open
        - jurisdiction: US Federal
        - description: subject or reason for the letter
        - source_url: current page URL

        Return a JSON object: {{"cases": [...]}}
        If no results are found, return {{"cases": []}}
        """

    def _normalize_result(self, raw_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        cases = _find_cases(raw_json)
        normalized = []
        for case in cases:
            if not isinstance(case, dict):
                continue
            case_id = (case.get("case_id") or case.get("letter_id")
                       or case.get("reference_number") or case.get("id") or "")
            employer = (case.get("employer_name") or case.get("company_name")
                        or case.get("firm") or case.get("name") or "")
            vtype = (case.get("violation_type") or case.get("violation_category")
                     or case.get("type") or "FDA Violation")
            penalty = (case.get("proposed_penalty") or case.get("penalty")
                       or case.get("penalty_amount") or 0)
            date = (case.get("decision_date") or case.get("issue_date")
                    or case.get("date") or "")
            status = (case.get("status") or "unknown").lower()
            desc = (case.get("description") or case.get("summary")
                    or case.get("subject") or "")
            url = (case.get("source_url") or case.get("url") or case.get("link")
                   or self.source.base_url)
            normalized.append({
                "case_id": str(case_id),
                "employer_name": str(employer),
                "violation_type": str(vtype),
                "proposed_penalty": penalty,
                "decision_date": str(date),
                "status": status,
                "jurisdiction": "US Federal",
                "description": str(desc),
                "source_url": str(url),
                "source": "FDA",
            })
        return normalized
