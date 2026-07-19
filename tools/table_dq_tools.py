"""
tools/table_dq_tools.py

Tools exposed to the single-table DQ orchestrator agent.
"""

from langchain.tools import tool

from tools.metadata_profiling import (
    get_schema,
    get_row_count,
    get_sample_rows,
    get_column_profile_stats,
    get_candidate_keys,
)
from tools.pk_inference import infer_simple_pk, infer_composite_pk


@tool
def extract_all_metadata(table_name: str) -> dict:
    """Profiles a table end-to-end and infers its Primary Key.

    Deterministically computes the schema, row count, sample rows, and
    per-column profile stats (null counts, distinct ratios), then finds
    every simple (single-column) Candidate Key. If at least one exists,
    the best one is chosen via infer_simple_pk; otherwise a composite
    key is proposed via infer_composite_pk. Returns all of the above
    plus the final inferred primary_key and the rationale behind it.

    Args:
        table_name: Name of the table (as registered in DuckDB) to profile.
    """
    schema = get_schema(table_name)
    row_count = get_row_count(table_name)
    sample_rows = get_sample_rows(table_name)
    column_stats = get_column_profile_stats(table_name, schema, row_count)
    candidate_keys = get_candidate_keys(column_stats, row_count)

    metadata = {
        "table_name": table_name,
        "schema": schema,
        "row_count": row_count,
        "sample_rows": sample_rows,
        "column_stats": column_stats,
        "candidate_keys": candidate_keys,
    }

    if candidate_keys:
        pk_result = infer_simple_pk(metadata)
        pk_inference_method = "simple"
    else:
        pk_result = infer_composite_pk(metadata)
        pk_inference_method = "composite"

    return {
        **metadata,
        "primary_key": pk_result.pk_columns,
        "pk_rationale": pk_result.rationale,
        "pk_inference_method": pk_inference_method,
    }


@tool
def create_rule_plan():
    """Creates Data Quality Rules list that must be checked"""
    return None


@tool
def generate_sql():
    """Generate SQL queries"""
    return None


@tool
def validate_sql():
    """Validates SQL queries"""
    return None


@tool
def execute_sql():
    """Executes SQL queries"""
    return None


@tool
def write_report():
    """Writes Data Quality Report (rule, sql query, output, inference)"""
    return None
