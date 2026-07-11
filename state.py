"""
Shared graph state.

Kept intentionally small - every field here is something more than one
node needs to read or write. Anything more local than that belongs
inside a single node function instead of on this object.
"""

from typing import Optional, TypedDict


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


class DQState(TypedDict):
    # Tables still waiting to be processed. current_table is NOT in this
    # list - it's popped off as soon as it becomes the active table.
    tables: list[str]
    current_table: str

    # Per-table working data. All of these are reset to their empty
    # values whenever the orchestrator moves on to a new table.
    metadata: Optional[TableMetadata]
    planned_checks: Optional[TableDQPlan]
    compiled_rules: Optional[TableRuleSet]
    validation_errors: list[str]
    sql_valid: bool
    execution_results: list[dict]
    retry_count: int

    # Grows across the entire run. Never reset between tables.
    dq_report: list[dict]

    # The orchestrator's routing decision for "what runs next". Read by
    # the graph's conditional edge right after the orchestrator node runs.
    next_agent: str


def initial_state(tables: list[str]) -> DQState:
    """Build the starting state for a run given the list of tables to
    process. The first table becomes current_table immediately."""
    first_table, *remaining = tables
    return DQState(
        tables=remaining,
        current_table=first_table,
        metadata=None,
        planned_checks=None,
        compiled_rules=None,
        validation_errors=[],
        sql_valid=False,
        execution_results=[],
        retry_count=0,
        dq_report=[],
        next_agent="",
    )