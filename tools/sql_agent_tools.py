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

    Returns:
    """
    


@tool
def append_result() -> :
    """
    Only once all the queries for a rule were executed to check it and a
    Data Quality issue was found, it is appended to the final output csv 
    file -dq_report.csv.

    Columns that the report must have -Rule, Queries, Output, Insight.

    The insight is found by an LLM call, by passing the first 3 columns and 
    a system prompt instructing it to create a one line insight based on this 
    information.

    Args:
    """
    