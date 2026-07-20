"""
tools/table_dq_tools.py

Tools exposed to the single-table DQ orchestrator agent.

Metadata and per-rule results are cached server-side, keyed by table_name,
in _metadata_hash and _result_hash. This avoids ever having the LLM
re-generate large payloads (full schema/sample rows, full violation
samples) as tool-call arguments just to relay data it already produced -
previously this duplicated the largest blobs in the conversation and was
the main driver of token usage. Tools that need that data look it up from
the cache themselves; what's returned to the orchestrator is a trimmed
summary, just enough to drive the Todo List and decide next steps.

Relies on main.py running tables strictly sequentially (one
table_dq_agent.invoke call completes before the next starts) - the cache
is not safe for concurrent runs across tables.
"""

from langchain.tools import tool

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
from tools.sql_generation import generate_sql_for_rule
from tools.sql_checks import validate_sql_query, execute_sql_query
from tools.report_insights import generate_insights
from tools.report_writer import append_report_rows
import config

# table_name -> full extract_all_metadata output (schema, sample_rows,
# column_stats, candidate_keys, near_candidate_keys, primary_key, ...)
_metadata_hash: dict[str, dict] = {}

# table_name -> list of full execute_sql_query outputs (including
# sample_violations) collected so far for that table
_result_hash: dict[str, list[dict]] = {}


@tool
def extract_all_metadata(table_name: str) -> dict:
    """Profiles a table end-to-end and infers its Primary Key.

    Deterministically computes the schema, row count, sample rows, and
    per-column profile stats (null counts, distinct ratios), then finds
    every candidate key - both strict (fully unique, non-null) and near
    (high distinct_ratio but not fully unique, which often signals the
    exact uniqueness issue you're meant to detect). Infers the primary
    key from these and caches the full profile against table_name for
    later tools to use internally.

    Args:
        table_name: Name of the table (as registered in DuckDB) to profile.

    Returns:
        A short summary only: table_name, row_count, column_count,
        primary_key, pk_inference_method. The full profile (schema,
        sample_rows, column_stats, candidate_keys, near_candidate_keys,
        pk_rationale) is cached internally - later tools that need it
        (create_rule_plan) look it up themselves by table_name, so you
        never need to relay it.
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

    full_metadata = {
        **metadata,
        "primary_key": pk_result.pk_columns,
        "pk_rationale": pk_result.rationale,
        "pk_inference_method": pk_inference_method,
    }
    _metadata_hash[table_name] = full_metadata

    return {
        "table_name": table_name,
        "row_count": row_count,
        "column_count": len(schema),
        "primary_key": full_metadata["primary_key"],
        "pk_inference_method": pk_inference_method,
    }


@tool
def create_rule_plan(table_name: str) -> dict:
    """Creates the full list of Data Quality rules to check for this table.

    Looks up the metadata cached by extract_all_metadata for this table
    and asks the LLM to propose every DQ check justified by the table's
    columns and stats, grounded in a generic rule-of-thumb prompt (see
    RULE_PLAN_SYSTEM_PROMPT) rather than table-specific hardcoded logic.

    Args:
        table_name: Name of the table (as registered in DuckDB) that was
            already profiled by extract_all_metadata in this run.

    Returns:
        The proposed rules (rule_name + description for each) - use these
        to populate your Todo List.
    """
    metadata = _metadata_hash[table_name]
    rule_plan = generate_rule_plan(metadata)
    return rule_plan.model_dump()


@tool
def generate_sql(table_name: str, rule: dict, previous_error: str = None) -> dict:
    """Writes a SQL "violations query" for one data quality rule: a SELECT
    that returns every row breaking the rule (zero rows back = it passes).
    Re-fetches the table's real schema itself, so column names are never
    guessed from what the orchestrator happens to relay.

    Args:
        table_name: Name of the table (as registered in DuckDB) to check.
        rule: One rule from create_rule_plan's output - a dict with
            rule_name and description.
        previous_error: If this is a retry after validate_sql failed, the
            error message from that failure, so the fix targets the actual
            problem instead of re-rolling a new query from scratch.
    """
    generated = generate_sql_for_rule(table_name, rule, previous_error)
    return {
        "rule_name": rule.get("rule_name"),
        "description": rule.get("description"),
        "sql": generated.sql,
    }


@tool
def validate_sql(sql: str) -> dict:
    """Validates a generated SQL query by actually running it: checks it's
    a single, read-only SELECT (rejects anything that could modify data or
    schema), then executes it against the live DuckDB catalog and data -
    catching both bad table/column references and data-dependent runtime
    errors (e.g. casting a value like '$423.12' to a numeric type) before
    execute_sql is trusted to run it for real.

    Args:
        sql: The SQL query text to validate.
    """
    return validate_sql_query(sql)


@tool
def execute_sql(table_name: str, sql: str, rule_name: str, description: str = None) -> dict:
    """Executes an already-validated violations query and caches the full
    result (including sample violating rows) internally against
    table_name, for write_report to use later.

    Args:
        table_name: Name of the table the rule was checked against.
        sql: The validated SQL query to run.
        rule_name: The rule this query checks, for labeling the result.
        description: The rule's description, from generate_sql's output -
            carried forward into the cached result for write_report to use.

    Returns:
        Only rule_name, passed, and violation_count - enough to mark the
        check complete on your Todo List. The full result (sql, sample
        violating rows) is cached internally, not shown to you here;
        write_report looks it up itself.
    """
    result = execute_sql_query(table_name, sql, rule_name)
    result["description"] = description
    _result_hash.setdefault(table_name, []).append(result)
    return {
        "rule_name": result["rule_name"],
        "passed": result["passed"],
        "violation_count": result["violation_count"],
    }


@tool
def write_report(table_name: str) -> dict:
    """Writes this table's DQ issues to the shared CSV report
    (config.REPORT_PATH), appending to any rows already written by other
    tables' runs - never overwrites it. Looks up every execute_sql result
    cached for this table itself (you don't need to relay them). Only
    rules that FAILED (found actual violations) are recorded; passing
    checks are left out of the report entirely. Generates one short
    plain-language insight per issue first (one batched LLM call for the
    whole table), then appends one row per issue with exactly 4 columns:
    rule, query, output, insight. Call this once, after every rule on this
    table's Todo List has been executed. Clears this table's cached
    results afterward.

    Args:
        table_name: Name of the table whose cached results (from every
            execute_sql call made in this run) should be reported and
            cleared.
    """
    results = _result_hash.pop(table_name, [])

    failed_results = [r for r in results if not r.get("passed")]
    insights = generate_insights(failed_results)
    rows_written = append_report_rows(failed_results, insights)
    return {
        "checks_evaluated": len(results),
        "issues_found": rows_written,
        "report_path": str(config.REPORT_PATH),
    }