"""
Deterministic DuckDB helpers.

One shared in-memory connection is used for the whole run. The graph is
sequential - only one node ever runs at a time - so there's no
concurrency to worry about, which means a single module-level connection
is simpler than threading a connection object through every function
call.
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
    """distinct_count and null_count per column. This is the signal the
    database agent's LLM call uses to reason about primary keys, instead
    of guessing from column names alone."""
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