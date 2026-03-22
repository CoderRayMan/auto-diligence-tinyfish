from dataclasses import dataclass
from typing import List


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]


def validate_request(target: str, query: str) -> ValidationResult:
    """Validate a research request for basic correctness."""
    errors = []

    if not target or not target.strip():
        errors.append("target must not be empty")
    elif len(target.strip()) < 2:
        errors.append("target must be at least 2 characters")
    elif len(target) > 500:
        errors.append("target must be under 500 characters")

    if not query or not query.strip():
        errors.append("query must not be empty")
    elif len(query) > 2000:
        errors.append("query must be under 2000 characters")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors)
