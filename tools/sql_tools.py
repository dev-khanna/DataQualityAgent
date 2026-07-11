"""
generate_sql, validate_sql, execute_sql.

generate_sql turns planned checks into DuckDB SQL that selects the rows
that VIOLATE each rule. Called once for the first pass; called again on
a retry, in which case it only touches the checks the validator flagged.
The retry cap is enforced right here, in code - not left to the
orchestrator's judgment, because past MAX_RETRIES the tool simply
refuses to burn another LLM call and tells the orchestrator to give up
instead.

validate_sql and execute_sql are fully deterministic - no LLM in either.
execute_sql refuses to run anything unless validate_sql has already
passed. That guard lives in the tool itself, not in a prompt, because
what it runs is real SQL against a real database.
"""

import re
from typing import TypedDict

from langchain_core.messages import ToolMessage
from langchain.tools import tool, ToolRuntime
from langgraph.types import Command

from config import FORBIDDEN_SQL_KEYWORDS, MAX_RETRIES, get_llm
from state import DQState, TableRuleSet
from utils.database import run_query

_GENERATOR_SYSTEM_PROMPT = """You are a SQL generation agent. You write DuckDB SQL
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


class _GeneratedRule(TypedDict):
    check_name: str
    column: str
    sql: str


class _SqlGenerationOutput(TypedDict):
    rules: list[_GeneratedRule]


def _generate(metadata: dict, checks: list[dict]) -> list[_GeneratedRule]:
    llm = get_llm().with_structured_output(_SqlGenerationOutput)
    result = llm.invoke([
        {"role": "system", "content": _GENERATOR_SYSTEM_PROMPT},
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


@tool
def generate_sql(runtime: ToolRuntime[None, DQState]) -> Command:
    """Write DuckDB SQL for the planned checks on the current table. On
    the first call, writes SQL for every planned check. If called again
    after validate_sql found problems, only regenerates the checks that
    failed. Refuses to run past the retry limit - call write_report
    instead once it tells you to."""
    state = runtime.state
    metadata = state["metadata"]
    planned_checks = state["planned_checks"]
    table_name = metadata["table_name"]
    validation_errors = state["validation_errors"]

    if not validation_errors:
        rules = _generate(metadata, planned_checks["checks"])
        compiled: TableRuleSet = {"table_name": table_name, "rules": rules}
        return Command(update={
            "compiled_rules": compiled,
            "validation_errors": [],
            "sql_valid": False,
            "messages": [ToolMessage(
                content=f"Generated SQL for {len(rules)} check(s).",
                tool_call_id=runtime.tool_call_id,
            )],
        })

    if state["retry_count"] >= MAX_RETRIES:
        return Command(update={
            "messages": [ToolMessage(
                content=(
                    f"Retry limit ({MAX_RETRIES}) already reached for table "
                    f"'{table_name}'. Do not call generate_sql or validate_sql "
                    f"again for this table - call write_report to record the "
                    f"failure."
                ),
                tool_call_id=runtime.tool_call_id,
            )],
        })

    failed_names = _failed_check_names(validation_errors)
    checks_by_name = {c["check_name"]: c for c in planned_checks["checks"]}
    errors_by_name = {
        error.split(":", 1)[0].strip(): error.split(":", 1)[1].strip()
        for error in validation_errors
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

    return Command(update={
        "compiled_rules": compiled,
        "validation_errors": [],
        "sql_valid": False,
        "retry_count": state["retry_count"] + 1,
        "messages": [ToolMessage(
            content=f"Regenerated SQL for failed check(s): {sorted(failed_names)}.",
            tool_call_id=runtime.tool_call_id,
        )],
    })


_KEYWORD_PATTERN = re.compile(
    r"\b(" + "|".join(FORBIDDEN_SQL_KEYWORDS) + r")\b", re.IGNORECASE
)


def _validate_one(sql: str) -> str | None:
    cleaned = sql.strip().rstrip(";")
    if not cleaned.upper().startswith("SELECT"):
        return "must be a single SELECT statement"
    if ";" in cleaned:
        return "only one statement is allowed"
    match = _KEYWORD_PATTERN.search(cleaned)
    if match:
        return f"contains forbidden keyword '{match.group(1).upper()}'"
    return None


@tool
def validate_sql(runtime: ToolRuntime[None, DQState]) -> Command:
    """Check the currently generated SQL for the current table: rejects
    anything that isn't a single read-only SELECT, and rejects any
    forbidden keyword (DROP, DELETE, UPDATE, etc). Deterministic - call
    this immediately after every generate_sql call."""
    rules = runtime.state["compiled_rules"]["rules"]
    errors = []
    for rule in rules:
        error = _validate_one(rule["sql"])
        if error:
            errors.append(f"{rule['check_name']}: {error}")

    sql_valid = len(errors) == 0
    summary = (
        "All checks passed validation."
        if sql_valid
        else f"{len(errors)} check(s) failed validation: {errors}"
    )

    return Command(update={
        "validation_errors": errors,
        "sql_valid": sql_valid,
        "messages": [ToolMessage(content=summary, tool_call_id=runtime.tool_call_id)],
    })


@tool
def execute_sql(runtime: ToolRuntime[None, DQState]) -> Command:
    """Run every validated check's SQL against DuckDB and record how
    many rows (if any) violate each rule. Refuses to run anything unless
    validate_sql has already passed for this table's current SQL."""
    state = runtime.state
    if not state["sql_valid"]:
        return Command(update={
            "messages": [ToolMessage(
                content="Cannot execute: SQL has not passed validation yet. Call validate_sql first.",
                tool_call_id=runtime.tool_call_id,
            )],
        })

    rules = state["compiled_rules"]["rules"]
    results = []
    for rule in rules:
        outcome = run_query(rule["sql"])
        results.append({
            "check_name": rule["check_name"],
            "column": rule["column"],
            "sql": rule["sql"],
            "row_count": outcome["row_count"],
            "sample_rows": outcome["sample_rows"],
        })

    violations = sum(1 for r in results if r["row_count"] > 0)

    return Command(update={
        "execution_results": results,
        "executed": True,
        "messages": [ToolMessage(
            content=f"Executed {len(results)} check(s); {violations} found violations.",
            tool_call_id=runtime.tool_call_id,
        )],
    })