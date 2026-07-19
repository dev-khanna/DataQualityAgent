"""
main.py

Entry point for the DQ pipeline.

1. Loads every CSV in DATA_DIR into DuckDB as a table.
2. Runs the single-table DQ orchestrator on each table, one at a time.
3. Runs the cross-table DQ orchestrator once every table has been
   checked individually. (not yet implemented)
"""

from config import DATA_DIR
from db import load_tables
from agents.table_dq_agent import table_dq_agent
from agents.cross_table_dq_agent import cross_table_dq_agent


def run_table_dq_checks(table_names: list[str]) -> None:
    for table in table_names:
        table_dq_agent.invoke(f"Run the Data Quality check on table {table}")


def run_cross_table_dq_checks() -> None:
    pass


if __name__ == "__main__":
    table_names = load_tables(DATA_DIR)
    run_table_dq_checks(table_names)
    run_cross_table_dq_checks()
