"""
tools/report.py

Deterministic report-writing, plus the single LLM call that turns a
rule's raw violation data into a one-line, plain-language insight (see
REPORT_INSIGHT_SYSTEM_PROMPT). Both are used by append_result once a rule
has been confirmed to have found a genuine data quality issue.
"""

import csv
import json
import os

from langchain_core.messages import SystemMessage, HumanMessage

import config
from llm import gemini_model
from prompts import REPORT_INSIGHT_SYSTEM_PROMPT
from schemas import ReportInsights

REPORT_FIELDNAMES = ["Rule", "Queries", "Output", "Insight"]


def generate_insight(rule_name: str, description: str, results: list[dict]) -> str:
    """Generate a concise, accurate plain-language insight for a failed rule.

    The LLM receives:
    - The exact deterministic violation count from SQL execution.
    - Only a small sample of violating rows.
    - The SQL query that produced the violations.

    The LLM does NOT receive the full violation dataset, reducing token usage.
    """

    structured_model = gemini_model.with_structured_output(ReportInsights)
    compact_results = []

    for result in results:
        compact_results.append(
            {
                "query": result["query"],
                "violation_count": result.get("row_count", len(result.get("rows", []))),
                "sample_violations": result.get("rows", [])[:3],
            }
        )

    rule_bundle = {
        "rule_name": rule_name,
        "description": description,
        "results": compact_results,
    }

    messages = [
        SystemMessage(content=REPORT_INSIGHT_SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(rule_bundle, default=str)),
    ]

    response = structured_model.invoke(messages)

    for insight in response.insights:
        if insight.rule_name == rule_name:
            return insight.insight

    # Fall back to whatever came back if the name didn't round-trip exactly.
    return response.insights[0].insight if response.insights else ""


def write_report_row(table_name: str, rule_name: str, results: list[dict], insight: str) -> None:
    """Appends one row to the shared dq_report.csv, writing the header
    only the first time the file is created. Never overwrites prior rows -
    every table's rules land in the same on-disk report (see
    INDIVIDUAL_TABLE_DQ_SYSTEM_PROMPT's <context>)."""
    is_new_file = not os.path.exists(config.REPORT_PATH)
    queries = [result["query"] for result in results]
    output = {result["query"]: result["rows"] for result in results}

    with open(config.REPORT_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_FIELDNAMES)
        if is_new_file:
            writer.writeheader()
        writer.writerow(
            {
                # table-qualified so two tables' rules never collide in one shared report
                "Rule": f"{table_name}.{rule_name}",
                "Queries": json.dumps(queries),
                "Output": json.dumps(output, default=str),
                "Insight": insight,
            }
        )


def reset_report() -> None:
    """Deletes dq_report.csv so the next run starts a fresh shared report.
    Optional - main.py leaves this commented out by default so a run can
    be resumed/extended rather than wiping prior tables' results."""
    if os.path.exists(config.REPORT_PATH):
        os.remove(config.REPORT_PATH)
