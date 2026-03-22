"""Reusable TinyFish goal prompt templates for regulatory research."""

import json


def build_generic_enforcement_goal(company_name: str, date_from: str, date_to: str) -> str:
    """Generic enforcement search goal template."""
    return f"""
    Search for regulatory enforcement actions and violations related to company: {company_name}.
    Filter results to date range: {date_from} to {date_to}.
    For each record extract:
    - case_id
    - employer_name
    - violation_type
    - proposed_penalty (numeric, USD)
    - decision_date (ISO 8601)
    - status (open | settled | closed | appealed)
    - jurisdiction
    - description
    - source_url
    Return a JSON object with a "cases" array.
    """


def build_login_goal(username: str, password: str) -> str:
    """Standard login flow goal."""
    return f"""
    1. Navigate to the login page.
    2. Enter username: {username}
    3. Enter password: {password}
    4. Click the login / sign-in button.
    5. Verify login succeeded by checking for a logout button, user menu, or dashboard.
    6. Return a JSON object: {{"logged_in": true/false, "signals": {{}}}}
    """


def render_goal_template(template: str, filters: dict) -> str:
    """Render a goal template with filter values."""
    rendered = template
    for key, value in filters.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
    return rendered
