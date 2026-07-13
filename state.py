"""
Shared graph state.

Metadata for every table is collected up front (see
tools/database_tools.py) and stored as ColumnInfo/TableMetadata,
BEFORE the agent loop ever starts - metadata_by_table is populated once
into the initial state and never mutated afterward. This is what lets
any tool (today: create_rule_plan; later: a cross-table check) reason
about every table at once, since nothing is fetched turn-by-turn.

Checks are tracked as a flat list spanning every table, each with its
OWN status and retry_count - a failing check for one table must not
block or re-trigger checks for a different table that already passed.

related_table on PlannedCheck/CompiledRule is unused today (always
None) - it exists now so that adding cross-table checks later is a
logic change in rule_tools.py/sql_tools.py, not a state migration.
"""
from typing import Literal, Optional, TypedDict

from langchain.agents import AgentState


class ColumnInfo(TypedDict):
    name: str
    type: str


class ColumnStat(TypedDict):
    """null_count/distinct_count for one column. Used both for the full
    per-column stats list (every column) and the candidate_keys subset
    (columns that are 0-null and fully unique)."""
    column: str
    null_count: int
    distinct_count: int


class TableMetadata(TypedDict):
    table_name: str
    row_count: int
    sample_rows: list[dict]
    columns: list[ColumnInfo]
    column_stats: list[ColumnStat]      # EVERY column, not just key candidates
    candidate_keys: list[ColumnStat]    # subset of column_stats: 0 nulls, fully unique
    primary_key: list[str]              # 1 column (simple) or 2+ (composite)
    is_composite: bool


class PlannedCheck(TypedDict):
    check_name: str                 # must be globally unique across ALL tables
    check_type: str
    table: str                      # table this check belongs to
    related_table: Optional[str]    # unused for now - reserved for future cross-table checks
    column: str
    description: str


class CompiledRule(TypedDict):
    check_name: str
    table: str
    related_table: Optional[str]
    column: str
    sql: str
    status: Literal["pending_validation", "valid", "invalid"]
    validation_error: Optional[str]
    retry_count: int


class DQState(AgentState):
    tables: list[str]
    metadata_by_table: dict[str, TableMetadata]
    planned_checks: list[PlannedCheck]
    compiled_rules: list[CompiledRule]
    execution_results: list[dict]
    dq_report: list[dict]


def initial_state_for_run(tables: list[str], metadata_by_table: dict[str, TableMetadata]) -> DQState:
    """Build the single starting state for the WHOLE run. Called once
    from main.py, after all tables' metadata has already been collected
    deterministically - the agent never has to call a metadata tool
    itself, it starts already knowing every table."""
    return DQState(
        messages=[{
            "role": "user",
            "content": (
                f"Run the data quality pipeline for {len(tables)} table(s): "
                f"{tables}. Metadata for every table has already been "
                f"collected and is available to you."
            ),
        }],
        tables=tables,
        metadata_by_table=metadata_by_table,
        planned_checks=[],
        compiled_rules=[],
        execution_results=[],
        dq_report=[],
    )