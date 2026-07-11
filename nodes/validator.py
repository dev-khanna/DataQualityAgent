"""
SQL Validator.

Deterministic, no LLM. Rejects anything that is not a single read-only
SELECT statement, and rejects any of the forbidden keywords.
"""

import re

from config import FORBIDDEN_SQL_KEYWORDS
from state import DQState

_KEYWORD_PATTERN = re.compile(
    r"\b(" + "|".join(FORBIDDEN_SQL_KEYWORDS) + r")\b", re.IGNORECASE
)


def _validate_one(sql: str) -> str | None:
    """Return an error message, or None if the SQL is fine."""
    cleaned = sql.strip().rstrip(";")

    if not cleaned.upper().startswith("SELECT"):
        return "must be a single SELECT statement"

    if ";" in cleaned:
        return "only one statement is allowed"

    match = _KEYWORD_PATTERN.search(cleaned)
    if match:
        return f"contains forbidden keyword '{match.group(1).upper()}'"

    return None


def sql_validator_node(state: DQState) -> dict:
    rules = state["compiled_rules"]["rules"]
    errors = []

    for rule in rules:
        error = _validate_one(rule["sql"])
        if error:
            errors.append(f"{rule['check_name']}: {error}")

    return {
        "validation_errors": errors,
        "sql_valid": len(errors) == 0,
    }