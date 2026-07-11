"""
Shared graph state.

`messages` is required by LangGraph's tool-calling loop - it's the
transcript the orchestrator LLM reads to decide which tool to call
next, and where each tool's result (as a ToolMessage) shows up right
after it runs. Everything else is pipeline state: progress on the table
being processed right now, plus the report that accumulates across the
whole run.

There's no `next_agent` field anymore - routing IS the tool call the LLM
makes each turn, so there's nothing left to store a routing decision in.
"""
from typing import Annotated, Optional, Sequence, TypedDict

from langchain.agents import AgentState
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ColumnInfo(TypedDict):
    column: str
    type: str


class TableMetadata(TypedDict):
    table_name: str
    columns: list[ColumnInfo]
    row_count: int
    sample_rows: list[dict]
    primary_key: str
    candidate_keys: list[str]


class PlannedCheck(TypedDict):
    check_name: str
    check_type: str
    column: str
    description: str


class TableDQPlan(TypedDict):
    table_name: str
    checks: list[PlannedCheck]


class CompiledRule(TypedDict):
    check_name: str
    column: str
    sql: str


class TableRuleSet(TypedDict):
    table_name: str
    rules: list[CompiledRule]


class DQState(AgentState):
    current_table: str
    metadata: Optional[TableMetadata]
    planned_checks: Optional[TableDQPlan]
    compiled_rules: Optional[TableRuleSet]
    validation_errors: list[str]
    sql_valid: bool
    execution_results: list[dict]
    executed: bool
    retry_count: int
    dq_report: list[dict]


def initial_state_for_table(table_name: str, dq_report_so_far: list[dict]) -> DQState:
    """Build the starting state for one table's agent run. Called once per table, from main.py's loop."""
    return DQState(
        messages=[{
            "role": "user",
            "content": f"Run the data quality pipeline for table '{table_name}'.",
        }],
        current_table=table_name,
        metadata=None,
        planned_checks=None,
        compiled_rules=None,
        validation_errors=[],
        sql_valid=False,
        execution_results=[],
        executed=False,
        retry_count=0,
        dq_report=dq_report_so_far
    )