"""
Database Intelligence agent.

Looks at one table and produces TableMetadata: schema, row count, sample
rows, primary key, and candidate keys.

An LLM makes the primary-key call because column names alone aren't
always reliable ("id" isn't always the key, "patient_id" sometimes is).
To keep that call grounded in the actual data rather than guesswork, it's
given real uniqueness/null statistics computed deterministically first.
"""

from typing import TypedDict

from config import get_llm
from state import DQState, TableMetadata
from utils.database import get_column_stats, get_row_count, get_sample_rows, get_schema

SYSTEM_PROMPT = """You are a database intelligence agent. You are given a
table's schema, row count, a few sample rows, and per-column uniqueness
statistics (distinct_count and null_count for every column).

Determine:
- primary_key: the single column that best identifies each row. A true
  primary key has null_count of 0 and distinct_count equal to the row
  count.
- candidate_keys: any other columns with that same property (zero nulls,
  fully unique), excluding whichever column you picked as primary_key.

If no column is a perfect fit, pick the closest one and say why in
notes.
"""


class PrimaryKeyAnalysis(TypedDict):
    primary_key: str
    candidate_keys: list[str]
    notes: str


def database_agent_node(state: DQState) -> dict:
    table_name = state["current_table"]

    schema = get_schema(table_name)
    row_count = get_row_count(table_name)
    sample_rows = get_sample_rows(table_name)
    column_stats = get_column_stats(table_name)

    llm = get_llm().with_structured_output(PrimaryKeyAnalysis)
    analysis = llm.invoke([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Table: {table_name}\n"
            f"Row count: {row_count}\n"
            f"Schema: {schema}\n"
            f"Sample rows: {sample_rows}\n"
            f"Column stats: {column_stats}\n"
        )},
    ])

    metadata: TableMetadata = {
        "table_name": table_name,
        "columns": schema,
        "row_count": row_count,
        "sample_rows": sample_rows,
        "primary_key": analysis["primary_key"],
        "candidate_keys": analysis["candidate_keys"],
    }
    return {"metadata": metadata}