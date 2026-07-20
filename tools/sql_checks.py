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
    """Checks that sql is safe (read-only, single statement) and
    syntactically valid against the live DuckDB catalog - without
    executing it. Uses EXPLAIN, which plans the query (catching bad
    table/column references and syntax errors) without running it."""
    read_only_error = _read_only_check(sql)
    if read_only_error:
        return {"is_valid": False, "errors": [read_only_error], "sql": sql}

    con = get_connection()
    try:
        con.execute(f"EXPLAIN {sql.strip().rstrip(';')}")
    except Exception as e:
        return {"is_valid": False, "errors": [str(e)], "sql": sql}

    return {"is_valid": True, "errors": [], "sql": sql}


def execute_sql_query(table_name: str, sql: str, rule_name: str, sample_limit: int = 5) -> dict:
    """Runs an already-validated violations query and reports whether the
    rule passed. passed = True iff the query returned zero rows."""
    con = get_connection()
    result = con.execute(sql.strip().rstrip(";"))
    columns = [desc[0] for desc in result.description]
    rows = result.fetchall()

    return {
        "rule_name": rule_name,
        "table_name": table_name,
        "sql": sql,
        "passed": len(rows) == 0,
        "violation_count": len(rows),
        "sample_violations": [dict(zip(columns, row)) for row in rows[:sample_limit]],
    }
