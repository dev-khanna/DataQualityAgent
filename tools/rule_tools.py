"""
Rule Creator tool.

Exposes create_rule_plan. Makes ONE LLM call across ALL tables at once
(metadata_by_table is already fully populated before this tool ever
runs). This ONLY plans single-table checks for now - cross-table checks
(e.g. referential integrity) are intentionally deferred, but
related_table already exists on PlannedCheck/CompiledRule (see
state.py) so adding them later is a prompt/logic change here, not a
state migration.
"""

from typing import TypedDict

from langchain_core.messages import ToolMessage
from langchain.tools import tool, ToolRuntime
from langgraph.types import Command

from config import get_llm, get_nvidia_llm
from state import DQState, PlannedCheck
from utils.helpers import read_knowledge_base

_SYSTEM_PROMPT = """You are a data quality rule planning agent.

You are given metadata for EVERY table in this database (schema,
primary key, sample rows) and a knowledge base describing single-table
data quality checks.

Plan checks using ONLY the knowledge base's single-table checks - do
NOT plan any check that requires comparing values across two tables
(e.g. do not attempt referential integrity / foreign key checks). Plan
checks independently for each table based on its own metadata.

For each check, provide:
- check_name: short, snake_case, GLOBALLY UNIQUE across every table
  (e.g. prefix with the table name if useful).
- check_type: a category from the knowledge base.
- table: the table this check belongs to.
- column: the column the check applies to.
- description: one sentence describing what the check verifies.

Do NOT write any SQL. Only plan checks against columns/tables that
actually exist in the metadata you were given.
"""


class _PlannedCheckOutput(TypedDict):
    check_name: str
    check_type: str
    table: str
    column: str
    description: str


class _RulePlanOutput(TypedDict):
    checks: list[_PlannedCheckOutput]


def _plan_checks(metadata_by_table: dict, knowledge_base: str) -> list[PlannedCheck]:
    llm = get_llm().with_structured_output(_RulePlanOutput)
    result = llm.invoke([
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Knowledge base:\n{knowledge_base}\n\n"
            f"Metadata for all tables:\n{metadata_by_table}\n"
        )},
    ])
    return [{**c, "related_table": None} for c in result["checks"]]


def _ensure_unique_names(checks: list[PlannedCheck]) -> list[PlannedCheck]:
    """Deterministic safety net: the LLM was told to keep names globally
    unique, but nothing enforces that. A collision here would corrupt
    per-check retry/status tracking downstream, so fix it in code
    rather than trusting the prompt."""
    seen: dict[str, int] = {}
    deduped = []
    for c in checks:
        name = c["check_name"]
        if name in seen:
            seen[name] += 1
            c = {**c, "check_name": f"{name}_{seen[name]}"}
        else:
            seen[name] = 0
        deduped.append(c)
    return deduped


@tool
def create_rule_plan(runtime: ToolRuntime[None, DQState]) -> Command:
    """Decide which single-table data quality checks should exist for
    this run, based on every table's metadata. Call once, before any
    SQL is written."""
    metadata_by_table = runtime.state["metadata_by_table"]

    if not metadata_by_table:
        return Command(update={
            "messages": [ToolMessage(
                content="Cannot plan checks: no table metadata is available for this run.",
                tool_call_id=runtime.tool_call_id,
            )],
        })

    knowledge_base = read_knowledge_base()
    checks = _ensure_unique_names(_plan_checks(metadata_by_table, knowledge_base))

    return Command(update={
        "planned_checks": checks,
        "messages": [ToolMessage(
            content=(
                f"Planned {len(checks)} check(s) across {len(metadata_by_table)} "
                f"table(s): {[c['check_name'] for c in checks]}."
            ),
            tool_call_id=runtime.tool_call_id,
        )],
    })