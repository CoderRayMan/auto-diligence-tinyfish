"""OSHA enforcement records agent."""

from __future__ import annotations

from typing import Any, Dict, List

from .base import BaseAgent, SourceConfig


def _find_cases(raw_json: Dict[str, Any]) -> List[Any]:
    """Locate the list of case records regardless of the key TinyFish used."""
    # Preferred key
    if "cases" in raw_json and isinstance(raw_json["cases"], list):
        return raw_json["cases"]
    # Other common keys TinyFish might use
    for key in ("inspections", "data", "results", "records", "items",
                "violations", "citations", "findings", "enforcement_actions"):
        if key in raw_json and isinstance(raw_json[key], list):
            return raw_json[key]
    # Fall back: return the first list value found in the dict
    for val in raw_json.values():
        if isinstance(val, list):
            return val
    return []


class OshaAgent(BaseAgent):
    """Scrapes OSHA enforcement inspection and citation records."""

    def _build_goal(self, target: str, query: str) -> str:
        return f"""YOUR TASK: Find OSHA enforcement inspections for \"{target}\" and return the results as a JSON object.

STEP 1: Go to https://www.osha.gov/ords/imis/establishment.html
STEP 2: Enter \"{target}\" in the Establishment Name field and submit the search.
STEP 3: You will see a results table. Read the inspection records from this table.
STEP 4: DO NOT click into any individual inspection links. Stay on the search results page.
STEP 5: From the visible results table, extract up to 10 records.

For each row in the results table, capture:
- case_id: the inspection number shown
- employer_name: the establishment name
- violation_type: the violation type if shown, otherwise "workplace safety"
- proposed_penalty: numeric penalty if shown, otherwise 0
- decision_date: the inspection open date in YYYY-MM-DD format
- status: open or closed
- jurisdiction: the state abbreviation shown
- description: any violation description shown, otherwise \"{query}\"
- source_url: the current page URL

OUTPUT: After reading the table, immediately return this JSON (no other text):
{{\"cases\": [{{\"case_id\": ..., \"employer_name\": ..., \"violation_type\": ..., \"proposed_penalty\": ..., \"decision_date\": ..., \"status\": ..., \"jurisdiction\": ..., \"description\": ..., \"source_url\": ...}}, ...]}}
If no results found, return: {{\"cases\": []}}
"""

    def _normalize_result(self, raw_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        cases = _find_cases(raw_json)
        normalized = []
        for case in cases:
            if not isinstance(case, dict):
                continue
            # Accept multiple field name variants TinyFish might use
            case_id = (case.get("case_id") or case.get("inspection_id")
                       or case.get("citation_number") or case.get("id") or "")
            employer = (case.get("employer_name") or case.get("establishment_name")
                        or case.get("company") or case.get("name") or "")
            vtype = (case.get("violation_type") or case.get("citation_type")
                     or case.get("type") or "serious")
            penalty = (case.get("proposed_penalty") or case.get("penalty")
                       or case.get("penalty_amount") or 0)
            date = (case.get("decision_date") or case.get("inspection_date")
                    or case.get("date") or "")
            status = (case.get("status") or "unknown").lower()
            desc = (case.get("description") or case.get("narrative")
                    or case.get("standard") or "")
            url = (case.get("source_url") or case.get("url") or case.get("link")
                   or self.source.base_url)
            normalized.append({
                "case_id": str(case_id),
                "employer_name": str(employer),
                "violation_type": str(vtype),
                "proposed_penalty": penalty,
                "decision_date": str(date),
                "status": status,
                "jurisdiction": (case.get("jurisdiction") or case.get("state")
                                  or "US Federal"),
                "description": str(desc),
                "source_url": str(url),
                "source": "OSHA",
            })
        return normalized
