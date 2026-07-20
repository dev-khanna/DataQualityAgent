"""
tools/sql_checks.py

Deterministic, non-LLM helpers for validate_sql and execute_sql. No LLM
calls happen in this file - it only ever runs SQL that's already been
generated, checking it's safe and syntactically valid, then executing it.
"""

import re

from db import get_connection

FORBIDDEN_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE",
    "ATTACH", "DETACH", "COPY", "EXPORT", "IMPORT", "PRAGMA", "CALL",
    "GRANT", "REVOKE", "TRUNCATE", "VACUUM", "INSTALL", "LOAD",
}


def _read_only_check(sql: str) -> str | None:
    """Returns an error message if sql isn't a safe, single, read-only
    SELECT statement - or None if it looks safe."""
    stripped = sql.strip().rstrip(";")

    if ";" in stripped:
        return "Multiple statements are not allowed - write exactly one query."

    if not stripped.upper().startswith(("SELECT", "WITH")):
        return "Query must be a single SELECT (or WITH ... SELECT) statement."

    tokens = set(re.findall(r"[A-Za-z_]+", stripped.upper()))
    forbidden_hit = tokens & FORBIDDEN_KEYWORDS
    if forbidden_hit:
        return f"Query contains disallowed keyword(s): {', '.join(sorted(forbidden_hit))}."

    return None


def validate_sql_query(sql: str) -> dict:
    """Checks that sql is safe (read-only, single statement) and valid
    against the live DuckDB catalog *and* data. Actually executes the
    query (safe — already confirmed read-only above) rather than just
    planning it with EXPLAIN, since EXPLAIN alone won't catch
    data-dependent runtime errors like CAST failures on malformed
    values (e.g. currency-formatted strings)."""
    read_only_error = _read_only_check(sql)
    if read_only_error:
        return {"is_valid": False, "errors": [read_only_error], "sql": sql}

    con = get_connection()
    try:
        con.execute(sql.strip().rstrip(";"))
    except Exception as e:
        return {"is_valid": False, "errors": [str(e)], "sql": sql}

    return {"is_valid": True, "errors": [], "sql": sql}


def execute_sql_query(table_name: str, sql: str, rule_name: str, sample_limit: int = 5) -> dict:
    """Runs an already-validated violations query. Never raises: if
    execution fails anyway, the failure is returned as part of the
    result instead of crashing the run."""
    con = get_connection()
    try:
        result = con.execute(sql.strip().rstrip(";"))
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
    except Exception as e:
        return {
            "rule_name": rule_name,
            "table_name": table_name,
            "sql": sql,
            "passed": False,
            "violation_count": None,
            "sample_violations": [],
            "error": str(e),
        }

    return {
        "rule_name": rule_name,
        "table_name": table_name,
        "sql": sql,
        "passed": len(rows) == 0,
        "violation_count": len(rows),
        "sample_violations": [dict(zip(columns, row)) for row in rows[:sample_limit]],
    }