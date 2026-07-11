"""
Rule Creator agent.

Looks at TableMetadata and the DQ knowledge base, and decides which DQ
checks should exist for this table. Produces a plan only - no SQL here,
that's the SQL Generator's job.
"""

from typing import TypedDict

from config import get_llm
from state import DQState, PlannedCheck, TableDQPlan
from utils.helpers import read_knowledge_base

SYSTEM_PROMPT = """You are a data quality rule planning agent.

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


class RulePlanOutput(TypedDict):
    checks: list[PlannedCheck]


def rule_creator_node(state: DQState) -> dict:
    metadata = state["metadata"]
    knowledge_base = read_knowledge_base()

    llm = get_llm().with_structured_output(RulePlanOutput)
    result = llm.invoke([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Knowledge base:\n{knowledge_base}\n\n"
            f"Table metadata:\n{metadata}\n"
        )},
    ])

    plan: TableDQPlan = {
        "table_name": metadata["table_name"],
        "checks": result["checks"],
    }
    return {"planned_checks": plan}