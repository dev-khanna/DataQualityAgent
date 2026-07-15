"""
Deterministic DuckDB helpers.

One shared in-memory connection is used for the whole run. The graph is
sequential - only one node ever runs at a time - so a single
module-level connection is simpler than threading one through every call.
"""

import os

import duckdb

_connection = None


def get_connection() -> duckdb.DuckDBPyConnection:
    global _connection
    if _connection is None:
        _connection = duckdb.connect(database=":memory:")
    return _connection


def load_tables(data_dir) -> list[str]:
    """Register every CSV file in data_dir as a DuckDB table, named after
    the file (without extension). Returns the table names in the order
    they were loaded."""
    con = get_connection()
    table_names = []
    for filename in sorted(os.listdir(data_dir)):
        if not filename.endswith(".csv"):
            continue
        table_name = os.path.splitext(filename)[0]
        path = os.path.join(data_dir, filename)
        con.execute(
            f'CREATE OR REPLACE TABLE "{table_name}" AS '
            f"SELECT * FROM read_csv_auto(?)",
            [path],
        )
        table_names.append(table_name)
    return table_names


def get_schema(table_name: str) -> list[dict]:
    con = get_connection()
    rows = con.execute(f'DESCRIBE "{table_name}"').fetchall()
    return [{"column": row[0], "type": row[1]} for row in rows]


def get_row_count(table_name: str) -> int:
    con = get_connection()
    return con.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]


def get_sample_rows(table_name: str, limit: int = 5) -> list[dict]:
    con = get_connection()
    columns = [c["column"] for c in get_schema(table_name)]
    rows = con.execute(f'SELECT * FROM "{table_name}" LIMIT {limit}').fetchall()
    return [dict(zip(columns, row)) for row in rows]


def get_column_stats(table_name: str) -> list[dict]:
    """distinct_count and null_count per column, for EVERY column - not
    just ones that turn out to be candidate keys. Kept for every column
    so future cross-table matching has cardinality signal to lean on
    beyond column naming alone."""
    con = get_connection()
    stats = []
    for col in get_schema(table_name):
        name = col["column"]
        distinct_count, null_count = con.execute(
            f'SELECT COUNT(DISTINCT "{name}"), COUNT(*) - COUNT("{name}") '
            f'FROM "{table_name}"'
        ).fetchone()
        stats.append({
            "column": name,
            "distinct_count": distinct_count,
            "null_count": null_count,
        })
    return stats


def get_combo_distinct_count(table_name: str, columns: list[str]) -> int:
    """Distinct-tuple count for a proposed composite key. Used to verify
    an LLM's composite key guess against the actual data - never trust
    a multi-column uniqueness claim without checking it."""
    con = get_connection()
    col_list = ", ".join(f'"{c}"' for c in columns)
    return con.execute(
        f'SELECT COUNT(*) FROM (SELECT DISTINCT {col_list} FROM "{table_name}") AS _combo'
    ).fetchone()[0]


def run_query(sql: str, sample_limit: int = 5) -> dict:
    """Run an already-validated SELECT statement. Returns the total row
    count plus a small sample of the returned rows."""
    con = get_connection()
    result = con.execute(sql)
    columns = [d[0] for d in result.description]
    sample_rows = [dict(zip(columns, row)) for row in result.fetchmany(sample_limit)]
    row_count = con.execute(
        f"SELECT COUNT(*) FROM ({sql.rstrip(';')}) AS _sub"
    ).fetchone()[0]
    return {"columns": columns, "sample_rows": sample_rows, "row_count": row_count}

_NUMERIC_TYPE_PREFIXES = (
    "TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT",
    "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT", "UHUGEINT",
    "FLOAT", "DOUBLE", "DECIMAL", "REAL",
)


def _is_numeric_type(sql_type: str) -> bool:
    return sql_type.upper().startswith(_NUMERIC_TYPE_PREFIXES)


def get_numeric_distribution_stats(table_name: str, schema: list[dict]) -> list[dict]:
    """Deterministic IQR-based distribution bounds for every numeric
    column: min, max, Q1, median, Q3, and the standard Tukey fence
    (Q1 - 1.5*IQR, Q3 + 1.5*IQR). This is the one thing the LLM should
    never be guessing at - magnitude/outlier checks (e.g. "expenses
    shouldn't be more than Nx coverage") should reference these real
    bounds instead of an invented multiplier.

    Takes `schema` as a parameter, unlike get_column_stats (which
    re-fetches it internally) - purely to avoid a redundant DESCRIBE
    round-trip, since every caller already has it computed. Minor,
    deliberate deviation from the existing per-function pattern.

    DECIMAL-typed columns come back from DuckDB as Python Decimal, not
    float - mixing Decimal and float in arithmetic raises TypeError
    (confirmed by hand), so every value is cast to float immediately
    after fetchone(), before any arithmetic happens. Skips non-numeric
    columns and numeric columns that are 100% null (q1/q3 come back
    NULL in that case - nothing to compute).
    """
    con = get_connection()
    stats = []
    for col in schema:
        name, sql_type = col["column"], col["type"]
        if not _is_numeric_type(sql_type):
            continue
        row = con.execute(f'''
            SELECT
                MIN("{name}"),
                MAX("{name}"),
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY "{name}"),
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY "{name}"),
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY "{name}")
            FROM "{table_name}"
            WHERE "{name}" IS NOT NULL
        ''').fetchone()
        if row[2] is None or row[3] is None:   # all-null numeric column
            continue
        col_min, col_max, q1, median, q3 = (float(v) for v in row)
        iqr = q3 - q1
        stats.append({
            "column": name,
            "min": col_min,
            "max": col_max,
            "q1": q1,
            "median": median,
            "q3": q3,
            "iqr_lower_bound": q1 - 1.5 * iqr,
            "iqr_upper_bound": q3 + 1.5 * iqr,
        })
    return stats