"""SEC enforcement actions agent."""

from __future__ import annotations

from typing import Any, Dict, List

from .base import BaseAgent, SourceConfig


def _find_cases(raw_json: Dict[str, Any]) -> List[Any]:
    """Locate the list of case records regardless of the key TinyFish used."""
    if "cases" in raw_json and isinstance(raw_json["cases"], list):
        return raw_json["cases"]
    for key in ("actions", "enforcement_actions", "litigation_releases",
                "data", "results", "records", "items", "violations", "findings"):
        if key in raw_json and isinstance(raw_json[key], list):
            return raw_json[key]
    for val in raw_json.values():
        if isinstance(val, list):
            return val
    return []


class SecAgent(BaseAgent):
    """Scrapes SEC enforcement actions, litigation releases, and orders."""

    def _build_goal(self, target: str, query: str) -> str:
        return f"""
        Navigate to {self.source.base_url} and search for SEC enforcement actions, litigation releases,
        and administrative orders involving company or individual: "{target}".
        Do NOT open individual case links. Extract only from the search results list.

        For each enforcement action visible in the results, extract:
        - case_id: SEC release number or litigation release number
        - employer_name: company or individual named
        - violation_type: type of securities violation (fraud, disclosure failure, insider trading, market manipulation)
        - proposed_penalty: disgorgement or civil penalty amount as a plain number with no $ or commas.
          Look carefully in the press release title and search snippet for amounts like
          "$20 million", "$20,000,000", "20 million penalty", etc. Use 0 only if no amount appears anywhere.
        - decision_date: date the action was announced (YYYY-MM-DD)
        - status: settled, litigated, or ongoing
        - jurisdiction: US Federal (SEC)
        - description: brief summary of the alleged violations, including any penalty amount mentioned
        - source_url: URL of the press release or order page shown

        Return a JSON object: {{"cases": [...]}}
        If no results are found, return {{"cases": []}}
        """

    def _normalize_result(self, raw_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        cases = _find_cases(raw_json)
        normalized = []
        for case in cases:
            if not isinstance(case, dict):
                continue
            case_id = (case.get("case_id") or case.get("release_number")
                       or case.get("litigation_release") or case.get("id") or "")
            employer = (case.get("employer_name") or case.get("company_name")
                        or case.get("defendant") or case.get("name") or "")
            vtype = (case.get("violation_type") or case.get("charge_type")
                     or case.get("type") or "Securities Violation")
            penalty = (case.get("proposed_penalty") or case.get("disgorgement")
                       or case.get("civil_penalty") or case.get("penalty") or 0)
            date = (case.get("decision_date") or case.get("announcement_date")
                    or case.get("date") or "")
            status = (case.get("status") or "unknown").lower()
            desc = (case.get("description") or case.get("summary")
                    or case.get("charges") or "")
            url = (case.get("source_url") or case.get("url") or case.get("link")
                   or self.source.base_url)
            normalized.append({
                "case_id": str(case_id),
                "employer_name": str(employer),
                "violation_type": str(vtype),
                "proposed_penalty": penalty,
                "decision_date": str(date),
                "status": status,
                "jurisdiction": "US Federal (SEC)",
                "description": str(desc),
                "source_url": str(url),
                "source": "SEC",
            })
        return normalized
