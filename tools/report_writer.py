"""
tools/report_writer.py

Deterministic CSV report writing - no LLM calls here. Appends one row per
rule to the shared report on disk; never overwrites it, since earlier,
separate runs may have already written other tables' results there (see
the <context> note in TABLE_DQ_SYSTEM_PROMPT). Writes the header only the
first time the file is created.
"""

import csv
import json

import config

REPORT_COLUMNS = ["rule", "query", "output", "insight"]


def _format_rule(result: dict) -> str:
    rule_name = result.get("rule_name", "")
    description = result.get("description")
    return f"{rule_name}: {description}" if description else rule_name


def _format_output(result: dict) -> str:
    if result.get("passed"):
        return "PASSED - 0 violations"
    if result.get("error"):
        return f"ERROR - query failed during execution: {result['error']}"
    sample = json.dumps(result.get("sample_violations", []), default=str)
    return f"FAILED - {result.get('violation_count', 0)} violation(s); sample: {sample}"


def reset_report() -> None:
    """Deletes any existing report file so a fresh pipeline run starts
    blank. Call exactly once, at the very start of the overall run in
    main.py — never per-table, since later tables are meant to append
    to earlier tables' results within the same run."""
    if config.REPORT_PATH.exists():
        config.REPORT_PATH.unlink()


def append_report_rows(results: list[dict], insights: dict[str, str]) -> int:
    """Appends one CSV row per result to config.REPORT_PATH. Returns the
    number of rows written."""
    if not results:
        return 0

    file_exists = config.REPORT_PATH.exists()
    config.REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(config.REPORT_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(REPORT_COLUMNS)
        for result in results:
            writer.writerow(
                [
                    _format_rule(result),
                    result.get("sql", ""),
                    _format_output(result),
                    insights.get(result.get("rule_name", ""), ""),
                ]
            )

    return len(results)
