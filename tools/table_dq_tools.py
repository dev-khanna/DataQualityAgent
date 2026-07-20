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
from tools.rule_planning import generate_rule_plan
from tools.sql_generation import generate_sql_for_rule
from tools.sql_checks import validate_sql_query, execute_sql_query
from tools.report_insights import generate_insights
from tools.report_writer import append_report_rows
import config


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
def create_rule_plan(metadata: dict) -> dict:
    """Creates the full list of Data Quality rules to check for this table.

    Asks the LLM to propose every DQ check justified by the table's
    columns and stats, grounded in a generic rule-of-thumb prompt (see
    RULE_PLAN_SYSTEM_PROMPT) rather than table-specific hardcoded logic.

    Args:
        metadata: The full metadata dict returned by extract_all_metadata
            (schema, row_count, sample_rows, column_stats, candidate_keys,
            primary_key, pk_rationale, pk_inference_method).
    """
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
    """Validates a generated SQL query without executing it: checks it's a
    single, read-only SELECT (rejects anything that could modify data or
    schema), then checks it's syntactically valid and references real
    tables/columns via DuckDB's query planner.

    Args:
        sql: The SQL query text to validate.
    """
    return validate_sql_query(sql)


@tool
def execute_sql(table_name: str, sql: str, rule_name: str, description: str = None) -> dict:
    """Executes an already-validated violations query and reports whether
    the rule passed - passed is True iff the query returned zero rows.
    Includes the violation count and a small sample of offending rows.
    Carries the rule's description forward so write_report doesn't need
    it re-supplied separately later.

    Args:
        table_name: Name of the table the rule was checked against.
        sql: The validated SQL query to run.
        rule_name: The rule this query checks, for labeling the result.
        description: The rule's description, from generate_sql's output -
            carried forward into this result for write_report to use.
    """
    result = execute_sql_query(table_name, sql, rule_name)
    result["description"] = description
    return result


@tool
def write_report(results: list[dict]) -> dict:
    """Writes this table's DQ issues to the shared CSV report
    (config.REPORT_PATH), appending to any rows already written by other
    tables' runs - never overwrites it. Only rules that FAILED (found
    actual violations) are recorded; passing checks are left out of the
    report entirely. Generates one short plain-language insight per issue
    first (one batched LLM call for the whole table), then appends one
    row per issue with exactly 4 columns: rule, query, output, insight.
    Call this once, after every rule on this table's Todo List has been
    executed.

    Args:
        results: The list of execute_sql outputs collected for every rule
            checked on this table (each with rule_name, description, sql,
            passed, violation_count, sample_violations) - pass all of
            them, including passing ones; this tool filters internally.
    """
    failed_results = [r for r in results if not r.get("passed")]
    insights = generate_insights(failed_results)
    rows_written = append_report_rows(failed_results, insights)
    return {
        "checks_evaluated": len(results),
        "issues_found": rows_written,
        "report_path": str(config.REPORT_PATH),
    }
