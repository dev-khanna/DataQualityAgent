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
from agents.individual_table_dq_agent import run_individual_table_dq_check
from tools.report import reset_report  
from tools.chain_before_sql_agent import reset_todo_list


def run_cross_table_dq_checks() -> None:
    pass


if __name__ == "__main__":
    reset_report()
    reset_todo_list()
    table_names = load_tables(DATA_DIR)
    print("CSV files loaded into DuckDB successfully.\n")

    print("Running individual table DQ checks pipeline..")
    for table in table_names:
        print(f"Running DQ check on table {table}...")
        run_individual_table_dq_check(table)
        print(f"{table} issues recorded successfully!")

    run_cross_table_dq_checks()

    print("DONE")
