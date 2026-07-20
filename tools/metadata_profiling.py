"""
tools/metadata_profiling.py

Deterministic, non-LLM helpers that extract_all_metadata composes to
profile a table. Every function here talks to DuckDB directly and
returns plain Python data structures - no LLM calls happen in this file.
"""

from typing import Any

from db import get_connection


def get_schema(table_name: str) -> list[dict[str, Any]]:
    """Column name + declared type for every column in the table."""
    con = get_connection()
    result = con.execute(f'DESCRIBE "{table_name}"')
    columns = [desc[0] for desc in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def get_row_count(table_name: str) -> int:
    con = get_connection()
    return con.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]


def get_sample_rows(table_name: str, limit: int = 5) -> list[dict[str, Any]]:
    con = get_connection()
    result = con.execute(f'SELECT * FROM "{table_name}" LIMIT {limit}')
    columns = [desc[0] for desc in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def get_column_profile_stats(
    table_name: str, schema: list[dict[str, Any]], row_count: int
) -> list[dict[str, Any]]:
    """Per-column null count, distinct count, and distinct ratio."""
    con = get_connection()
    stats = []
    for col in schema:
        column_name = col["column_name"]
        null_count, distinct_count = con.execute(
            f'SELECT COUNT(*) FILTER (WHERE "{column_name}" IS NULL), '
            f'COUNT(DISTINCT "{column_name}") FROM "{table_name}"'
        ).fetchone()
        distinct_ratio = (distinct_count / row_count) if row_count else 0.0
        stats.append(
            {
                "column_name": column_name,
                "data_type": col["column_type"],
                "null_count": null_count,
                "distinct_count": distinct_count,
                "distinct_ratio": round(distinct_ratio, 4),
            }
        )
    return stats


def get_candidate_keys(column_stats: list[dict[str, Any]], row_count: int) -> list[str]:
    """Every single column that is fully unique and non-null on its own -
    i.e. every valid simple Candidate Key."""
    if row_count == 0:
        return []
    return [
        stat["column_name"]
        for stat in column_stats
        if stat["null_count"] == 0 and stat["distinct_count"] == row_count
    ]
