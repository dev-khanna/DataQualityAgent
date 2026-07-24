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

import os

import config
from tools.metadata_profiling import (
    get_schema,
    get_row_count,
    get_sample_rows,
    get_column_profile_stats,
    get_low_cardinality_value_counts,
    get_text_anomaly_stats,
    get_candidate_keys,
    get_near_candidate_keys,
)
from tools.pk_inference import infer_simple_pk, infer_composite_pk
from tools.rule_planning import generate_rule_plan
from tools.rule_registry import register_rule
from schemas import RulePlan


def extract_metadata(table_name: str) -> dict:
    """Profiles a table end-to-end and infers its Primary Key. Fully
    deterministic except for the single PK-inference LLM call.

    Computes the schema, row count, sample rows, and per-column profile
    stats (null counts, distinct ratios, - for low-cardinality columns,
    raw value counts, and - for every VARCHAR column - blank/whitespace/
    casing/encoding/placeholder anomaly counts), finds every candidate
    key - both strict (fully unique, non-null) and near (high
    distinct_ratio but not fully unique, which often signals the exact
    uniqueness issue a DQ check is meant to catch) - and infers the
    primary key from those.

    The anomaly counts exist because a 20-row sample can easily contain
    zero examples of a real but low-prevalence issue (stray whitespace,
    mojibake, a lazy placeholder value) purely by chance - these are
    computed over the whole table instead, so the rule planner has an
    exact number instead of having to get lucky with the sample (see
    RULE_PLAN_SYSTEM_PROMPT's <input> section).

    Returns the full metadata dict: table_name, schema, row_count,
    sample_rows, column_stats, candidate_keys, near_candidate_keys, 
    primary_key, pk_rationale, pk_inference_method.
    """
    schema = get_schema(table_name)
    row_count = get_row_count(table_name)
    sample_rows = get_sample_rows(table_name)
    column_stats = get_column_profile_stats(table_name, schema, row_count)

    low_cardinality_value_counts = get_low_cardinality_value_counts(table_name, column_stats)
    text_anomaly_stats = get_text_anomaly_stats(table_name, schema)
    for stat in column_stats:
        stat["low_cardinality_value_counts"] = low_cardinality_value_counts.get(
            stat["column_name"]
        )
        anomalies = text_anomaly_stats.get(stat["column_name"], {})
        stat["blank_count"] = anomalies.get("blank_count")
        stat["whitespace_count"] = anomalies.get("whitespace_count")
        stat["casing_anomaly_count"] = anomalies.get("casing_anomaly_count")
        stat["encoding_anomaly_count"] = anomalies.get("encoding_anomaly_count")
        stat["placeholder_count"] = anomalies.get("placeholder_count")

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


def plan_rules(metadata: dict) -> RulePlan:
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
    _write_rules_to_todo_list(metadata["table_name"], rule_plan.rules)
    return rule_plan


def reset_todo_list() -> None:
    """Deletes todo_list.md so each run starts from a clean file instead
    of appending yet another table's rules onto whatever earlier runs
    already left behind. Nothing in the pipeline ever reads this file
    back in - the ReAct orchestrator gets its rules from the in-memory
    HumanMessage built in run_individual_table_dq_check, not from disk -
    so it's purely a write-only audit log and safe to clear. Mirrors
    tools/report.py's reset_report(): same reasoning, same pattern, just
    for the todo list instead of the CSV report.
    """
    if os.path.exists(config.TODO_DIR):
        os.remove(config.TODO_DIR)


def _write_rules_to_todo_list(table_name: str, rules: list) -> None:
    """Appends this table's freshly planned rules to todo_list.md (never
    overwritten within a run - new rules are appended for every table
    processed in that run; call reset_todo_list() once at the start of a
    run if you want a clean file), and registers each rule's description
    in the rule_registry so the ReAct orchestrator's tools can look it up
    later by (table_name, rule_name) alone, without needing the LLM to
    repeat it on every tool call."""
    with open(config.TODO_DIR, "a") as f:
        f.write(f"\n<!-- table: {table_name} -->\n")
        for rule in rules:
            f.write(f"{{'{rule.rule_name}': '{rule.description}'}}: pending\n")
            register_rule(table_name, rule.rule_name, rule.description)