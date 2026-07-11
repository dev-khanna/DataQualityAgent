"""
Rule Creator tool.

Exposes create_rule_plan. Internally reads the DQ knowledge base and
makes one LLM call to decide which checks make sense for this table -
no SQL here, only intent; that's generate_sql's job.
"""

from typing import Annotated, TypedDict

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from config import get_llm
from state import DQState, PlannedCheck, TableDQPlan
from utils.helpers import read_knowledge_base

_SYSTEM_PROMPT = """You are a data quality rule planning agent.

You are given metadata about a database table (schema, primary key,
sample rows) and a knowledge base describing the categories of data
quality checks this organization uses.

Decide which checks should be planned for this table. For each check,
provide:
- check_name: a short, unique, snake_case name
- check_type: one of the categories from the knowledge base
- column: the column it applies to
- description: one sentence describing what the check verifies

Do NOT write any SQL. You are only planning what to check, not how to
check it. Only plan checks that make sense given the columns that
actually exist in this table.
"""


class _RulePlanOutput(TypedDict):
    checks: list[PlannedCheck]


def _plan_checks(metadata: dict, knowledge_base: str) -> list[PlannedCheck]:
    llm = get_llm().with_structured_output(_RulePlanOutput)
    result = llm.invoke([
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Knowledge base:\n{knowledge_base}\n\n"
            f"Table metadata:\n{metadata}\n"
        )},
    ])
    return result["checks"]


@tool
def create_rule_plan(
    state: Annotated[DQState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Decide which data quality checks should exist for the current
    table, based on its metadata and the organization's DQ knowledge
    base. Call this after extract_database_metadata and before
    generate_sql - checks must be planned before any SQL can be written
    for them."""
    metadata = state["metadata"]
    knowledge_base = read_knowledge_base()
    checks = _plan_checks(metadata, knowledge_base)

    plan: TableDQPlan = {"table_name": metadata["table_name"], "checks": checks}

    return Command(update={
        "planned_checks": plan,
        "messages": [ToolMessage(
            content=f"Planned {len(checks)} check(s): {[c['check_name'] for c in checks]}.",
            tool_call_id=tool_call_id,
        )],
    })