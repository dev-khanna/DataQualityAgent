"""
DQ Report Writer tool.

Records one row per check that ran and found violations, plus one row
per check that never got valid SQL within the retry limit - both
per-CHECK now, spanning every table in the run.
"""

import csv

from langchain_core.messages import ToolMessage
from langchain.tools import tool, ToolRuntime
from langgraph.types import Command

from config import MAX_RETRIES, REPORT_PATH
from state import DQState

_FIELDNAMES = ["Rule", "Table", "RelatedTable", "Query", "Output", "Insight"]


def _rows_for_executed_checks(state: DQState) -> list[dict]:
    rows = []
    for result in state["execution_results"]:
        if result["row_count"] == 0:
            continue
        rows.append({
            "Rule": result["check_name"], "Table": result["table"],
            "RelatedTable": result["related_table"] or "",
            "Query": result["sql"], "Output": f"{result['row_count']} row(s) returned",
            "Insight": (
                f"{result['row_count']} row(s) in column '{result['column']}' "
                f"of '{result['table']}' violate check '{result['check_name']}'."
            ),
        })
    return rows


def _rows_for_permanently_failed_checks(state: DQState) -> list[dict]:
    rows = []
    for rule in state["compiled_rules"]:
        if rule["status"] == "invalid" and rule["retry_count"] >= MAX_RETRIES:
            rows.append({
                "Rule": rule["check_name"], "Table": rule["table"],
                "RelatedTable": rule["related_table"] or "",
                "Query": "", "Output": "not executed",
                "Insight": (
                    f"SQL for check '{rule['check_name']}' on '{rule['table']}' "
                    f"never passed validation after {MAX_RETRIES} retries. "
                    f"Last error: {rule['validation_error']}"
                ),
            })
    return rows


def _write_report_to_disk(dq_report: list[dict]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
        writer.writeheader()
        writer.writerows(dq_report)


def read_report_from_disk() -> list[dict]:
    if not REPORT_PATH.exists():
        return []
    with open(REPORT_PATH, newline="") as f:
        return list(csv.DictReader(f))


@tool
def write_report(runtime: ToolRuntime[None, DQState]) -> Command:
    """Record every check's results and persist to disk. Call once, as
    the last step - after execute_sql has run for every valid check and
    no fixable checks remain."""
    state = runtime.state

    still_fixable = [r["check_name"] for r in state["compiled_rules"]
                      if r["status"] == "invalid" and r["retry_count"] < MAX_RETRIES]
    if still_fixable:
        return Command(update={
            "messages": [ToolMessage(
                content=f"Cannot write report yet: {still_fixable} still have retries remaining.",
                tool_call_id=runtime.tool_call_id,
            )],
        })

    executed_names = {res["check_name"] for res in state["execution_results"]}
    not_yet_executed = [r["check_name"] for r in state["compiled_rules"]
                         if r["status"] == "valid" and r["check_name"] not in executed_names]
    if not_yet_executed:
        return Command(update={
            "messages": [ToolMessage(
                content=f"Cannot write report yet: {not_yet_executed} are valid but not executed.",
                tool_call_id=runtime.tool_call_id,
            )],
        })

    new_rows = _rows_for_executed_checks(state) + _rows_for_permanently_failed_checks(state)
    dq_report = state["dq_report"] + new_rows
    _write_report_to_disk(dq_report)

    return Command(update={
        "dq_report": dq_report,
        "messages": [ToolMessage(
            content=f"Report written - {len(new_rows)} row(s) across {len(state['tables'])} table(s).",
            tool_call_id=runtime.tool_call_id,
        )],
    })