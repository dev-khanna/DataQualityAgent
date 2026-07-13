"""
Database Intelligence.

No longer exposed to the orchestrator as a tool - metadata for every
table must exist BEFORE the agent loop starts, so main.py calls
extract_all_metadata() directly, once, before building the initial
state.

Key-finding logic (Option B - no combinatorial search):
1. Deterministically find every single column that is 0-null and
   100%-unique (a candidate key).
2. If any exist, ask the LLM to pick ONE as the primary key.
3. If none exist, ask the LLM to propose a composite key from the full
   column stats, then deterministically verify that guess against the
   real data - an unverified multi-column uniqueness claim would
   silently break every check planned against this table.
"""

from typing import TypedDict

from config import get_llm
from state import ColumnStat, ColumnInfo, TableMetadata
from utils.database import (
    get_column_stats,
    get_combo_distinct_count,
    get_row_count,
    get_sample_rows,
    get_schema,
)

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

Only choose from the candidates listed above. If no column is a perfect
fit, pick the closest one and say why in notes.
"""

_COMPOSITE_KEY_PROMPT = """You are a database intelligence agent. No single
column in this table is both fully non-null and fully unique, so no
single-column primary key exists.

You are given the table's schema, row count, sample rows, and per-column
uniqueness statistics (distinct_count and null_count for every column).

Reason about the table's grain (what one row represents) and identify
the smallest combination of columns - normally 2, occasionally 3 - that
together would have exactly one distinct combination per row. Favor
columns with low null_count and high distinct_count.

Only choose columns that exist in the schema. Explain your reasoning in
notes - this guess will be checked against the real data afterward.
"""


class _PrimaryKeyAnalysis(TypedDict):
    primary_key: str
    candidate_keys: list[str]
    notes: str


class _CompositeKeyAnalysis(TypedDict):
    primary_key_columns: list[str]
    notes: str


def _pick_primary_key(
    table_name: str, schema: list[dict], row_count: int,
    sample_rows: list[dict], column_stats: list[dict],
    stat_derived_candidates: list[str],
) -> _PrimaryKeyAnalysis:
    llm = get_llm().with_structured_output(_PrimaryKeyAnalysis)
    return llm.invoke([
        {"role": "system", "content": _PRIMARY_KEY_PROMPT},
        {"role": "user", "content": (
            f"Table: {table_name}\nRow count: {row_count}\nSchema: {schema}\n"
            f"Sample rows: {sample_rows}\nColumn stats: {column_stats}\n"
            f"stat_derived_candidates: {stat_derived_candidates}\n"
        )},
    ])


def _pick_composite_key(
    table_name: str, schema: list[dict], row_count: int,
    sample_rows: list[dict], column_stats: list[dict],
) -> _CompositeKeyAnalysis:
    llm = get_llm().with_structured_output(_CompositeKeyAnalysis)
    return llm.invoke([
        {"role": "system", "content": _COMPOSITE_KEY_PROMPT},
        {"role": "user", "content": (
            f"Table: {table_name}\nRow count: {row_count}\nSchema: {schema}\n"
            f"Sample rows: {sample_rows}\nColumn stats: {column_stats}\n"
        )},
    ])


def _verify_composite_key(
    table_name: str, columns: list[str], row_count: int, column_stats: list[dict],
) -> str:
    stats_by_col = {c["column"]: c for c in column_stats}
    null_cols = [c for c in columns if stats_by_col.get(c, {}).get("null_count", 0) > 0]
    distinct_count = get_combo_distinct_count(table_name, columns)

    if distinct_count == row_count and not null_cols:
        return "verified: this combination is unique and non-null."
    issues = []
    if distinct_count != row_count:
        issues.append(f"only {distinct_count}/{row_count} distinct combinations")
    if null_cols:
        issues.append(f"nulls present in {null_cols}")
    return f"UNVERIFIED - {'; '.join(issues)}."


def build_table_metadata(table_name: str) -> TableMetadata:
    """Collect schema/stats and determine the primary key (simple or
    composite) for ONE table."""
    schema = get_schema(table_name)
    row_count = get_row_count(table_name)
    sample_rows = get_sample_rows(table_name)
    column_stats_raw = get_column_stats(table_name)   # every column

    candidate_keys: list[ColumnStat] = [
        {"column": c["column"], "null_count": c["null_count"], "distinct_count": c["distinct_count"]}
        for c in column_stats_raw
        if c["null_count"] == 0 and c["distinct_count"] == row_count
    ]

    if candidate_keys:
        stat_derived_candidates = [c["column"] for c in candidate_keys]
        analysis = _pick_primary_key(
            table_name, schema, row_count, sample_rows, column_stats_raw, stat_derived_candidates
        )
        primary_key = [analysis["primary_key"]]
        is_composite = False
    else:
        analysis = _pick_composite_key(table_name, schema, row_count, sample_rows, column_stats_raw)
        primary_key = analysis["primary_key_columns"]
        is_composite = True
        note = _verify_composite_key(table_name, primary_key, row_count, column_stats_raw)
        print(f"  [{table_name}] composite key {primary_key}: {note}")

    columns: list[ColumnInfo] = [{"name": c["column"], "type": c["type"]} for c in schema]
    column_stats: list[ColumnStat] = [
        {"column": c["column"], "null_count": c["null_count"], "distinct_count": c["distinct_count"]}
        for c in column_stats_raw
    ]

    return TableMetadata(
        table_name=table_name,
        row_count=row_count,
        sample_rows=sample_rows,
        columns=columns,
        column_stats=column_stats,
        candidate_keys=candidate_keys,
        primary_key=primary_key,
        is_composite=is_composite,
    )


def extract_all_metadata(tables: list[str]) -> dict[str, TableMetadata]:
    """Batch entry point, called once from main.py before the agent
    starts. Each table is wrapped in its own try/except so one bad
    table doesn't take down metadata collection for every other table."""
    metadata_by_table = {}
    for table_name in tables:
        try:
            metadata_by_table[table_name] = build_table_metadata(table_name)
        except Exception as e:
            print(f"!! Metadata extraction failed for '{table_name}', skipping: {e}")
    return metadata_by_table