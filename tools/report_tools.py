"""
DQ Report Writer tool.

Exposes write_report. Deterministic - no LLM. Records either the
per-check violations found for this table, or a single failure row if
validation never passed, and persists the whole accumulated report to
disk immediately.
"""

import csv

from langchain_core.messages import ToolMessage
from langchain.tools import tool, ToolRuntime
from langgraph.types import Command

from config import REPORT_PATH
from state import DQState

_FIELDNAMES = ["Rule", "Query", "Output", "Insight"]


def _rows_for_successful_run(state: DQState) -> list[dict]:
    rows = []
    for result in state["execution_results"]:
        if result["row_count"] == 0:
            continue
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
        writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
        writer.writeheader()
        writer.writerows(dq_report)


def read_report_from_disk() -> list[dict]:
    """Read back the cumulative report written so far. main.py uses this
    instead of trusting create_agent's invoke() return value, since that
    isn't guaranteed to include custom DQState fields like dq_report -
    only what write_report has actually persisted to disk is reliable."""
    if not REPORT_PATH.exists():
        return []
    with open(REPORT_PATH, newline="") as f:
        return list(csv.DictReader(f))


@tool
def write_report(runtime: ToolRuntime[None, DQState]) -> Command:
    """Record this table's results to the DQ report and persist it to
    disk. Call this once execute_sql has run, or once you've been told
    the retry limit was reached - it's always the last step for a
    table."""
    state = runtime.state
    if state["sql_valid"] and not state["executed"]:
        return Command(update={
            "messages": [ToolMessage(
                content="Cannot write report yet: execute_sql has not run. Call execute_sql first.",
                tool_call_id=runtime.tool_call_id,
            )],
        })

    if state["sql_valid"]:
        new_rows = _rows_for_successful_run(state)
    else:
        new_rows = _rows_for_failed_validation(state)

    dq_report = state["dq_report"] + new_rows
    _write_report_to_disk(dq_report)

    return Command(update={
        "dq_report": dq_report,
        "messages": [ToolMessage(
            content=f"Report updated - {len(new_rows)} row(s) added for this table.",
            tool_call_id=runtime.tool_call_id,
        )],
    })