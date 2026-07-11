"""
Database Intelligence tool.

Exposes exactly one business-level action: extract_database_metadata.
Everything it takes to produce that - pulling schema/row count/sample
rows/column stats from DuckDB, a deterministic pre-filter for candidate
keys, and the one LLM call that makes the final primary-key judgment -
is private to this file and never visible to the orchestrator.
"""

from typing import Annotated, TypedDict

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from config import get_llm
from state import DQState, TableMetadata
from utils.database import get_column_stats, get_row_count, get_sample_rows, get_schema

_PRIMARY_KEY_PROMPT = """You are a database intelligence agent. You are given a
table's schema, row count, a few sample rows, per-column uniqueness
statistics (distinct_count and null_count for every column), and a
deterministically pre-filtered list of columns that already satisfy the
zero-null / fully-unique property (stat_derived_candidates).

Determine:
- primary_key: the single column that best identifies each row. Prefer
  a column from stat_derived_candidates if one exists and makes sense
  given the table's apparent grain - but use your judgment if the data
  suggests otherwise (e.g. a column literally named "id" should usually
  win over an incidentally-unique column).
- candidate_keys: any other columns with that same property, excluding
  whichever column you picked as primary_key.

If no column is a perfect fit, pick the closest one and say why in
notes.
"""


class _PrimaryKeyAnalysis(TypedDict):
    primary_key: str
    candidate_keys: list[str]
    notes: str


def _discover_candidate_keys(row_count: int, column_stats: list[dict]) -> list[str]:
    """Deterministic pass: any column with zero nulls and a distinct
    count equal to the row count could serve as a key. This narrows what
    the LLM has to reason about instead of asking it to spot uniqueness
    from raw stats alone."""
    return [
        col["column"] for col in column_stats
        if col["null_count"] == 0 and col["distinct_count"] == row_count
    ]


def _pick_primary_key(
    table_name: str, schema: list[dict], row_count: int,
    sample_rows: list[dict], column_stats: list[dict],
    stat_derived_candidates: list[str],
) -> _PrimaryKeyAnalysis:
    llm = get_llm().with_structured_output(_PrimaryKeyAnalysis)
    return llm.invoke([
        {"role": "system", "content": _PRIMARY_KEY_PROMPT},
        {"role": "user", "content": (
            f"Table: {table_name}\n"
            f"Row count: {row_count}\n"
            f"Schema: {schema}\n"
            f"Sample rows: {sample_rows}\n"
            f"Column stats: {column_stats}\n"
            f"stat_derived_candidates: {stat_derived_candidates}\n"
        )},
    ])


@tool
def extract_database_metadata(
    state: Annotated[DQState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Collect schema, row count, sample rows, and column statistics for
    the current table, and determine its primary key and candidate keys.
    Call this first, before planning or writing any checks - every later
    step depends on this table's metadata being known."""
    table_name = state["current_table"]

    schema = get_schema(table_name)
    row_count = get_row_count(table_name)
    sample_rows = get_sample_rows(table_name)
    column_stats = get_column_stats(table_name)
    stat_derived_candidates = _discover_candidate_keys(row_count, column_stats)

    analysis = _pick_primary_key(
        table_name, schema, row_count, sample_rows, column_stats, stat_derived_candidates
    )

    metadata: TableMetadata = {
        "table_name": table_name,
        "columns": schema,
        "row_count": row_count,
        "sample_rows": sample_rows,
        "primary_key": analysis["primary_key"],
        "candidate_keys": analysis["candidate_keys"],
    }

    return Command(update={
        "metadata": metadata,
        "messages": [ToolMessage(
            content=(
                f"Metadata collected for '{table_name}': {row_count} rows, "
                f"primary_key='{metadata['primary_key']}', "
                f"candidate_keys={metadata['candidate_keys']}."
            ),
            tool_call_id=tool_call_id,
        )],
    })