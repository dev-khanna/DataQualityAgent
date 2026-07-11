"""
DQ Report Writer.

Deterministic, no LLM. Appends a row to the report for every check that
found an issue - passing checks are not recorded. Also saves the
accumulated report to disk after every table, so progress is never lost
even if a later table fails.
"""

import csv

from config import REPORT_PATH
from state import DQState

FIELDNAMES = ["Rule", "Query", "Output", "Insight"]


def _rows_for_successful_run(state: DQState) -> list[dict]:
    rows = []
    for result in state["execution_results"]:
        if result["row_count"] == 0:
            continue  # check passed - do not record
        rows.append({
            "Rule": result["check_name"],
            "Query": result["sql"],
            "Output": f"{result['row_count']} row(s) returned",
            "Insight": (
                f"{result['row_count']} row(s) in column "
                f"'{result['column']}' violate check '{result['check_name']}'."
            ),
        })
    return rows


def _rows_for_failed_validation(state: DQState) -> list[dict]:
    return [{
        "Rule": "ALL_RULES",
        "Query": "",
        "Output": "not executed",
        "Insight": (
            f"Skipped execution for table '{state['current_table']}': "
            f"SQL validation failed after {state['retry_count']} retries. "
            f"Errors: {'; '.join(state['validation_errors'])}"
        ),
    }]


def _write_report_to_disk(dq_report: list[dict]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(dq_report)


def report_writer_node(state: DQState) -> dict:
    if state["sql_valid"]:
        new_rows = _rows_for_successful_run(state)
    else:
        new_rows = _rows_for_failed_validation(state)

    dq_report = state["dq_report"] + new_rows
    _write_report_to_disk(dq_report)

    return {"dq_report": dq_report}