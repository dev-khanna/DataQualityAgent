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


def get_text_anomaly_stats(
    table_name: str, schema: list[dict[str, Any]]
) -> dict[str, dict[str, int]]:
    """For every VARCHAR column, computes whole-table, deterministic
    counts for five things a 20-row sample can easily miss entirely when
    the real prevalence is low (see RULE_PLAN_SYSTEM_PROMPT's <input>
    section for how these feed the rule planner):

    - blank_count: rows that are NULL or a whitespace-only string.
      Broader than null_count - a true empty CSV field is already folded
      into NULL by read_csv_auto, but a "   " value is not, and is still
      functionally missing.
    - whitespace_count: non-blank rows with leading/trailing whitespace.
    - casing_anomaly_count: non-blank, letter-containing rows whose case
      doesn't match whichever of {all-uppercase, all-lowercase, mixed}
      is dominant for this column. A column that's normally Title Case
      (city names) flags its ALL CAPS / all lower rows; a column that's
      normally all-uppercase (state codes) would instead flag any
      lowercase/mixed stragglers - the check is symmetric, it doesn't
      assume which convention is "correct" ahead of time.
    - encoding_anomaly_count: rows containing a likely mojibake sequence
      (config.MOJIBAKE_PATTERN). Heuristic, not exhaustive.
    - placeholder_count: rows matching a common lazy-default/sentinel
      string (config.PLACEHOLDER_VALUES), case-insensitive after
      trimming.

    None of these counts are a verdict on their own - a nonzero
    casing_anomaly_count on a column that's legitimately free text, for
    instance, doesn't mean much. They exist so the rule planner has an
    exact, whole-table number to reason over (clue 1) instead of having
    to notice the issue in a small sample by chance (clue 3).

    Returns a dict keyed by column_name; non-VARCHAR columns are absent.
    """
    import config
    con = get_connection()
    stats = {}
    for col in schema:
        if col["column_type"] != "VARCHAR":
            continue
        column_name = col["column_name"]
        placeholder_list = ", ".join(f"'{v}'" for v in config.PLACEHOLDER_VALUES)

        blank_count, whitespace_count, encoding_anomaly_count, placeholder_count, upper_ct, lower_ct, mixed_ct = con.execute(
            f'SELECT '
            f'COUNT(*) FILTER (WHERE "{column_name}" IS NULL OR TRIM("{column_name}") = \'\'), '
            f'COUNT(*) FILTER (WHERE "{column_name}" IS NOT NULL AND "{column_name}" != TRIM("{column_name}")), '
            f'COUNT(*) FILTER (WHERE "{column_name}" IS NOT NULL AND regexp_matches("{column_name}", \'{config.MOJIBAKE_PATTERN}\')), '
            f'COUNT(*) FILTER (WHERE "{column_name}" IS NOT NULL AND LOWER(TRIM("{column_name}")) IN ({placeholder_list})), '
            f'COUNT(*) FILTER (WHERE regexp_matches("{column_name}", \'[A-Za-z]\') AND "{column_name}" = UPPER("{column_name}") AND "{column_name}" != LOWER("{column_name}")), '
            f'COUNT(*) FILTER (WHERE regexp_matches("{column_name}", \'[A-Za-z]\') AND "{column_name}" = LOWER("{column_name}") AND "{column_name}" != UPPER("{column_name}")), '
            f'COUNT(*) FILTER (WHERE regexp_matches("{column_name}", \'[A-Za-z]\') AND "{column_name}" != UPPER("{column_name}") AND "{column_name}" != LOWER("{column_name}")) '
            f'FROM "{table_name}"'
        ).fetchone()

        total_lettered = upper_ct + lower_ct + mixed_ct
        dominant = max(upper_ct, lower_ct, mixed_ct) if total_lettered else 0
        casing_anomaly_count = total_lettered - dominant

        stats[column_name] = {
            "blank_count": blank_count,
            "whitespace_count": whitespace_count,
            "casing_anomaly_count": casing_anomaly_count,
            "encoding_anomaly_count": encoding_anomaly_count,
            "placeholder_count": placeholder_count,
        }
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