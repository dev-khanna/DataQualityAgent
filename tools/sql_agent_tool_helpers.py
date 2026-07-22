"""
tools/sql_agent_tool_helpers.py

Deterministic, non-LLM helper behind the orchestrator's single SQL tool
(execute_sql). No LLM calls happen in this file - it only ever validates
and executes SQL the orchestrator already wrote.
"""

import re

import config
import duckdb

from db import get_connection


def safety_check(sql: list[str]) -> dict[str, str]:
    """
    Checks that every query in the list is a single, read-only SELECT (or
    WITH ... SELECT) statement, and that none of them contain any DML or
    DDL keywords from FORBIDDEN_KEYWORDS.

    Returns a dict mapping each unsafe query to a short explanation of why
    it was rejected. An empty dict means every query in the list is safe -
    so `if safety_check(sql):` is true exactly when something is wrong.
    """
    errors: dict[str, str] = {}
    for query in sql:
        stripped = query.strip()
        body = stripped[:-1] if stripped.endswith(";") else stripped

        if ";" in body:
            errors[query] = (
                "Only one SQL statement is allowed per list entry - "
                "don't chain multiple statements together with semicolons."
            )
            continue

        if not re.match(r"(?is)^\s*(SELECT|WITH)\b", body):
            errors[query] = "Only SELECT or WITH ... SELECT statements are allowed."
            continue

        forbidden_found = [
            keyword
            for keyword in config.FORBIDDEN_KEYWORDS
            if re.search(rf"(?i)\b{keyword}\b", body)
        ]
        if forbidden_found:
            errors[query] = (
                f"Query contains forbidden keyword(s): {', '.join(forbidden_found)}. "
                "Only pure read-only SELECT statements are allowed."
            )

    return errors


def validate_and_execute(sql: list[str]) -> dict:
    """
    Check docstring of execute_sql to understand its use.

    Runs safety_check first; if anything is unsafe, none of the queries
    are executed and the offending ones are flagged with their reason.
    Otherwise, runs every query against DuckDB. If any query errors at
    runtime, none of the results are kept and the offending ones are
    flagged with their error message instead.

    Returns one of:
    - {"status": "validation_failed", "sql_query_list": {query: error_or_None}}
    - {"status": "runtime_error", "sql_query_list": {query: error_or_None}}
    - {"status": "ok", "results": [{"query": ..., "rows": [...], "row_count": ...}]}
      "rows" is capped at config.MAX_VIOLATION_ROWS_SHOWN - "row_count" is
      always the true, uncapped total.

    In the two error cases, every query from the original list is present
    as a key - queries mapped to None weren't flagged and are already
    fine, per <workflow> step 3.
    """
    validation_errors = safety_check(sql)
    if validation_errors:
        return {
            "status": "validation_failed",
            "sql_query_list": {query: validation_errors.get(query) for query in sql},
        }

    con = get_connection()
    results = []
    runtime_errors: dict[str, str] = {}

    for query in sql:
        try:
            cursor = con.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            results.append({
                "query": query,
                "rows": rows[: config.MAX_VIOLATION_ROWS_SHOWN],
                "row_count": len(rows),
            })
        except duckdb.Error as e:
            runtime_errors[query] = str(e)

    if runtime_errors:
        return {
            "status": "runtime_error",
            "sql_query_list": {query: runtime_errors.get(query) for query in sql},
        }

    return {"status": "ok", "results": results}
