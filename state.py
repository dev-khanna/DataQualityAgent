"""
Shared graph state.

Metadata for every table is collected up front, all at once (see
tools/database_tools.py) - BUT the single-table agent itself runs ONCE
PER TABLE (see orchestrator.run_single_table_detection), each time with
a fresh DQState scoped to just that one table. `tables` and
`metadata_by_table` will contain exactly one entry during a real run;
the fields stay list/dict-shaped only so cross_table.py can eventually
reuse this same TypedDict for a run that legitimately spans many tables
at once.

`dq_report` is the one field that is NOT reset per table: each table's
initial state is seeded with whatever is already written to disk (via
tools.report_tools.read_report_from_disk), so write_report always
appends this table's rows to the running, cross-table total instead of
overwriting it. This is what makes "one agent run per table" behave
like one continuous report on disk.

Checks (planned_checks/compiled_rules) are tracked as a flat list, but
because each run is scoped to one table, that list only ever holds
this table's checks - status/retry_count never need to be
disambiguated across tables, since different tables never share state.

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
    candidate_keys: Optional[list[ColumnStat]]  # 0-null/fully-unique columns; None if no simple CK exists
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


def initial_state_for_run(
    tables: list[str],
    metadata_by_table: dict[str, TableMetadata],
    dq_report: Optional[list[dict]] = None,
) -> DQState:
    """Build the starting state for ONE agent run - in practice, one
    run per table (see orchestrator.run_single_table_detection). The
    metadata for `tables` has already been collected deterministically,
    so the agent never has to call a metadata tool itself.

    `dq_report` should be seeded with whatever is already on disk (see
    tools.report_tools.read_report_from_disk) so write_report appends
    to the running total across tables instead of starting over."""
    return DQState(
        messages=[{
            "role": "user",
            "content": (
                f"Run the data quality pipeline for {len(tables)} table(s): "
                f"{tables}. Metadata for {'this table' if len(tables) == 1 else 'these tables'} "
                f"has already been collected and is available to you."
            ),
        }],
        tables=tables,
        metadata_by_table=metadata_by_table,
        planned_checks=[],
        compiled_rules=[],
        execution_results=[],
        dq_report=dq_report or [],
    )