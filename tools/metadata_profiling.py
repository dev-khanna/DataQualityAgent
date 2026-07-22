"""
tools/metadata_profiling.py

Deterministic, non-LLM helpers that extract_metadata composes to
profile a table. Every function here talks to DuckDB directly and
returns plain Python data structures. No LLM calls happen in this file.
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


def get_sample_rows(table_name: str, limit: int = None) -> list[dict[str, Any]]:
    import config
    limit = limit or config.SAMPLE_ROWS_LIMIT
    con = get_connection()
    result = con.execute(
        f'SELECT * FROM "{table_name}" USING SAMPLE {limit} ROWS (reservoir)'
    )
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


def get_low_cardinality_value_counts(
    table_name: str, column_stats: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """For every column with a small enough distinct_count to plausibly be
    a closed set of categories, returns its raw value -> row count
    breakdown, most frequent first. Columns above the threshold - almost
    certainly free text, identifiers, or numeric measures - are skipped,
    since a full value list wouldn't be "low cardinality" material and
    would just bloat the metadata sent to the LLM.

    Returns a dict keyed by column_name; columns that don't qualify are
    simply absent from it.
    """
    import config
    con = get_connection()
    value_counts = {}
    for stat in column_stats:
        distinct_count = stat["distinct_count"]
        if distinct_count == 0 or distinct_count > config.LOW_CARDINALITY_MAX_DISTINCT:
            continue
        column_name = stat["column_name"]
        rows = con.execute(
            f'SELECT "{column_name}" AS value, COUNT(*) AS count '
            f'FROM "{table_name}" WHERE "{column_name}" IS NOT NULL '
            f'GROUP BY "{column_name}" ORDER BY count DESC'
        ).fetchall()
        value_counts[column_name] = [{"value": v, "count": c} for v, c in rows]
    return value_counts


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


def get_near_candidate_keys(column_stats: list[dict[str, Any]], row_count: int) -> list[str]:
    """Columns that look like they were meant to be unique identifiers
    (no nulls, high distinct_ratio) but fall short of it in the actual
    data. The shortfall is usually itself the DQ issue - not proof the
    column is the wrong PK choice."""
    import config
    if row_count == 0:
        return []
    return [
        stat["column_name"]
        for stat in column_stats
        if stat["null_count"] == 0
        and config.NEAR_CANDIDATE_KEY_THRESHOLD <= stat["distinct_ratio"] < 1.0
    ]
