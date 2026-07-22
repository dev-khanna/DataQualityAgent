"""
main.py

Entry point for the DQ pipeline.

1. Loads every CSV in DATA_DIR into DuckDB as a table.
2. Runs the single-table DQ pipeline on each table, one at a time: a
   deterministic metadata + rule-planning chain, followed by the ReAct
   orchestrator that checks off the resulting todo list.
3. Runs the cross-table DQ orchestrator once every table has been
   checked individually. (not yet implemented)
"""

from config import DATA_DIR
from db import load_tables
from dataqualityagent.agents.individual_table_dq_agent import run_individual_table_dq_check
from agents.cross_table_dq_agent import cross_table_dq_agent


def run_cross_table_dq_checks() -> None:
    pass


if __name__ == "__main__":
    #reset_report()
    table_names = load_tables(DATA_DIR)

    for table in table_names:
        run_individual_table_dq_check(table)

    run_cross_table_dq_checks()
