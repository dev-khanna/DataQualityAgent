"""
db.py

DuckDB connection management and CSV loading utilities.
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
