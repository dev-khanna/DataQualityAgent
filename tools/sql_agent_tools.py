"""
tools/sql_agent.py

Tools exposed to the single-table DQ ReAct orchestrator. By design there
are only two:
  - execute_sql: validates and executes the list of SQL queries the orchestrator
    wrote itself for ONE rule.
  - append_result: appends a completed rule's outcome to the shared report iff 
    the SQL query returns something and it's a confirmed data quality issue.

todo_list.md has the initial set of rules that need to be checked. However, there 
may come a moment where the agent wants to create new rules to check in the todo list. 
Therefore, it must be edited, maintained and followed as per the requirements of sql_agent.
"""

from langchain.tools import tool

import config
from tools.sql_agent_tool_helpers import validate_and_execute
from tools.rule_registry import get_rule_description, pop_results, store_results, set_status
from tools.report import generate_insight, write_report_row

# Counts fix-and-retry attempts per (table_name, rule_name), so execute_sql
# can drop a rule automatically once MAX_RETRIES is exhausted (see
# INDIVIDUAL_TABLE_DQ_SYSTEM_PROMPT's <workflow> step 3).
_attempts: dict[tuple[str, str], int] = {}


@tool
def execute_sql(table_name: str, rule_name: str, sql: list[str]) -> dict:
    """
    Validates and executes a list of SQL queries against the DuckDB database, 
    for one data quality rule.

    This function executes in the following manner:
    -Check if the query is safe. It must not contain any DML or DDL keywords 
     that are provided in FORBIDDEN_KEYWORDS. If it does, we pass the list of 
     all the sql queries for the rule back to sql_agent in the following format: 
     {sql_query_list: {incorrect_query: error_message}}
    -If safe, we move on to executing the SQL query. During execution, if a
     runtime error comes up, we pass the list of all the sql queries for the 
     rule back to sql_agent in the following format: 
     {sql_query_list: {incorrect_query: error_message}}
    
    A limit of MAX_RETRIES is established. And if errors still persist, we drop
    the rule.

    The SELECT queries can be multiline/nested and multiple things such as window
    functions can even be used to check rules, as long as it's in accordance with 
    the appropriate DuckDB syntax.

    Some rules need more than one query to be checked completely, which is why a list
    is passed.

    Args:
        table_name: the table this rule's queries run against.
        rule_name: which rule this batch of queries belongs to.
        sql: every SELECT / WITH ... SELECT query this rule needs, as a list.

    Returns:
        On success: {"status": "ok", "results": [{"query", "rows", "row_count"}, ...]}
        On a validation or runtime problem: {"status": ..., "sql_query_list": {query: error_or_None}}
        Once retries are exhausted: {"status": "dropped", "message": ...} - stop
        retrying this rule and move on.
    """
    key = (table_name, rule_name)
    result = validate_and_execute(sql)

    if result["status"] == "ok":
        _attempts.pop(key, None)
        store_results(table_name, rule_name, result["results"])
        set_status(table_name, rule_name, "completed")
        return {"status": "ok", "results": result["results"]}

    attempts = _attempts.get(key, 0) + 1
    _attempts[key] = attempts

    if attempts > config.MAX_RETRIES:
        _attempts.pop(key, None)
        set_status(table_name, rule_name, "completed")
        return {
            "status": "dropped",
            "message": (
                f"Rule '{rule_name}' dropped after {config.MAX_RETRIES} failed "
                "fix-and-retry attempts. Do not call execute_sql for this rule "
                "again - mark it dropped on the todo list and move to the next rule."
            ),
        }

    return {"status": result["status"], "sql_query_list": result["sql_query_list"]}


@tool
def append_result(table_name: str, rule_name: str) -> dict:
    """
    Only once all the queries for a rule were executed to check it and a
    Data Quality issue was found, it is appended to the final output csv 
    file -dq_report.csv.

    Columns that the report must have -Rule, Queries, Output, Insight.

    The insight is found by an LLM call, by passing the first 3 columns and 
    a system prompt instructing it to create a one line insight based on this 
    information.

    Args:
        table_name: the table this rule was checked against.
        rule_name: which rule's result to append - must be a rule whose
            queries already ran cleanly via execute_sql and returned
            violating rows for this table.

    Returns:
        On success: {"status": "ok", "results": [{"query", "rows", "row_count"}, ...]}
        `rows` is capped at a small sample per query - `row_count` is
        always the true total, so use it (not len(rows)) to judge how
        many rows actually violate the rule.
        On a validation or runtime problem: {"status": ..., "sql_query_list": {query: error_or_None}}
        Once retries are exhausted: {"status": "dropped", "message": ...} - stop
        retrying this rule and move on.
    """
    results = pop_results(table_name, rule_name)
    if results is None:
        return {
            "status": "error",
            "message": (
                f"No successful query results found for rule '{rule_name}' on "
                f"table '{table_name}'. Call execute_sql for this rule first, "
                "and only call append_result once it returns violating rows."
            ),
        }

    description = get_rule_description(table_name, rule_name) or ""
    insight = generate_insight(rule_name, description, results)
    write_report_row(table_name, rule_name, results, insight)

    return {"status": "ok", "insight": insight}
