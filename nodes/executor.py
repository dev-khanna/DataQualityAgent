"""
SQL Executor.

Deterministic, no LLM. Runs every validated rule's SQL against DuckDB and
records how many rows (if any) violate the rule.
"""

from state import DQState
from utils.database import run_query


def sql_executor_node(state: DQState) -> dict:
    rules = state["compiled_rules"]["rules"]
    results = []

    for rule in rules:
        outcome = run_query(rule["sql"])
        results.append({
            "check_name": rule["check_name"],
            "column": rule["column"],
            "sql": rule["sql"],
            "row_count": outcome["row_count"],
            "sample_rows": outcome["sample_rows"],
        })

    return {"execution_results": results}