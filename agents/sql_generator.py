"""
SQL Generator agent.

Turns planned DQ checks into executable DuckDB SQL. Each check's SQL is
written to select the rows that VIOLATE the rule - zero rows back means
the check passed.

On a retry (validation_errors is not empty), this agent only asks the
LLM to fix the checks that failed. Every other rule in compiled_rules is
left exactly as it was - "do not regenerate every rule" is enforced
structurally here, not just by prompting.
"""

from typing import TypedDict

from config import get_llm
from state import DQState, TableRuleSet

SYSTEM_PROMPT = """You are a SQL generation agent. You write DuckDB SQL
for data quality checks.

For each planned check, write ONE SELECT statement that returns the rows
which VIOLATE the rule. For example, a "not null" check on column
"email" should select the rows where email IS NULL. A uniqueness check
should select the duplicate rows. A referential integrity check should
select rows whose foreign key value does not exist in the referenced
table.

Rules:
- SELECT statements only. Never write DROP, DELETE, UPDATE, INSERT,
  ALTER, CREATE, TRUNCATE, MERGE, CALL, or REPLACE.
- Reference the table by its exact name, double-quoted.
- Each query must be a single SELECT statement - no semicolons inside it.
- Add "LIMIT 200" to every query so results stay a reasonable size.
- If you are given a previous_error for a check, that means your last
  attempt at that check's SQL was rejected - fix that specific problem.
"""


class GeneratedRule(TypedDict):
    check_name: str
    column: str
    sql: str


class SqlGenerationOutput(TypedDict):
    rules: list[GeneratedRule]


def _generate(metadata: dict, checks: list[dict]) -> list[GeneratedRule]:
    llm = get_llm().with_structured_output(SqlGenerationOutput)
    result = llm.invoke([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Table name: {metadata['table_name']}\n"
            f"Schema: {metadata['columns']}\n"
            f"Checks to write SQL for:\n{checks}\n"
        )},
    ])
    return result["rules"]


def _failed_check_names(validation_errors: list[str]) -> set[str]:
    """Validation errors are formatted as 'check_name: message'."""
    return {error.split(":", 1)[0].strip() for error in validation_errors}


def sql_generator_node(state: DQState) -> dict:
    metadata = state["metadata"]
    planned_checks = state["planned_checks"]
    table_name = metadata["table_name"]

    if not state["validation_errors"]:
        # Fresh generation: write SQL for every planned check.
        rules = _generate(metadata, planned_checks["checks"])
        compiled: TableRuleSet = {"table_name": table_name, "rules": rules}
        return {
            "compiled_rules": compiled,
            "validation_errors": [],
            "sql_valid": False,
        }

    # Regeneration: only redo the checks the validator flagged. Everything
    # else in compiled_rules stays untouched.
    failed_names = _failed_check_names(state["validation_errors"])
    checks_by_name = {c["check_name"]: c for c in planned_checks["checks"]}
    errors_by_name = {
        error.split(":", 1)[0].strip(): error.split(":", 1)[1].strip()
        for error in state["validation_errors"]
    }

    checks_to_fix = [
        {**checks_by_name[name], "previous_error": errors_by_name[name]}
        for name in failed_names
        if name in checks_by_name
    ]

    fixed_rules = _generate(metadata, checks_to_fix)
    fixed_by_name = {rule["check_name"]: rule for rule in fixed_rules}

    updated_rules = [
        fixed_by_name.get(rule["check_name"], rule)
        for rule in state["compiled_rules"]["rules"]
    ]
    compiled: TableRuleSet = {"table_name": table_name, "rules": updated_rules}

    return {
        "compiled_rules": compiled,
        "validation_errors": [],
        "sql_valid": False,
        "retry_count": state["retry_count"] + 1,
    }