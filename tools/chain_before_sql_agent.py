"""
tools/chain_before_sql_agent.py

1. Metadata extraction + PK inference, then rule planning. These are
   chained together as plan function calls (tools/dq_chain.py).
   Neither of them is a tool the sql_agent (react agent) can call.

2. The resulting data quality rules to check are written to todo_list.md, 
   where new rules are appended for each table that's processed.  
   Each rule is appended in the todo list in the form of a dictionary in
   the following format:  {{rule_name: rule_description}: status}
   As per my understanding, the todo list automatically assigns the status.
"""

from tools.metadata_profiling import (
    get_schema,
    get_row_count,
    get_sample_rows,
    get_column_profile_stats,
    get_candidate_keys,
    get_near_candidate_keys,
)
from tools.pk_inference import infer_simple_pk, infer_composite_pk
from tools.rule_planning import generate_rule_plan


def extract_metadata(table_name: str) -> dict:
    """Profiles a table end-to-end and infers its Primary Key. Fully
    deterministic except for the single PK-inference LLM call.

    Computes the schema, row count, sample rows, and per-column profile
    stats (null counts, distinct ratios), finds every candidate key -
    both strict (fully unique, non-null) and near (high distinct_ratio
    but not fully unique, which often signals the exact uniqueness issue
    a DQ check is meant to catch) - and infers the primary key from
    those.

    Returns the full metadata dict: table_name, schema, row_count,
    sample_rows, column_stats, candidate_keys, near_candidate_keys,
    low_cardinality_value_counts, primary_key, pk_rationale,
    pk_inference_method.
    """
    schema = get_schema(table_name)
    row_count = get_row_count(table_name)
    sample_rows = get_sample_rows(table_name)
    column_stats = get_column_profile_stats(table_name, schema, row_count)
    candidate_keys = get_candidate_keys(column_stats, row_count)
    near_candidate_keys = get_near_candidate_keys(column_stats, row_count)

    metadata = {
        "table_name": table_name,
        "schema": schema,
        "row_count": row_count,
        "sample_rows": sample_rows,
        "column_stats": column_stats,
        "candidate_keys": candidate_keys,
        "near_candidate_keys": near_candidate_keys,
    }

    if candidate_keys:
        pk_result = infer_simple_pk(metadata)
        pk_inference_method = "simple"
    elif near_candidate_keys:
        pk_result = infer_simple_pk(metadata)
        pk_inference_method = "simple_near_unique"
    else:
        pk_result = infer_composite_pk(metadata)
        pk_inference_method = "composite"

    return {
        **metadata,
        "primary_key": pk_result.pk_columns,
        "pk_rationale": pk_result.rationale,
        "pk_inference_method": pk_inference_method,
    }


def plan_rules() -> :
    """
    Given metadata from extract_metadata, this function asks the 
    LLM to propose every DQ check justified by the table's columns 
    and stats (see RULE_PLAN_SYSTEM_PROMPT).

    A list of {rule_name: description} dictionaries are written to 
    todo_list.md.
    
    The rules generated here form the basis of the entire project 
    as this is where the appropriate data quality checks are issued
    for the table, given its metadata.
    """
    rule_plan = generate_rule_plan(metadata)
    
