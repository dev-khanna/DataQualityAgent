"""
tools/sql_agent_tool_helpers.py

Deterministic, non-LLM helper behind the orchestrator's single SQL tool
(check_sql). No LLM calls happen in this file - it only ever validates
and executes SQL the orchestrator already wrote.
"""

import re
import config

from db import get_connection


def safety_check(sql: list[str]) -> str | None:
    """
    Checks that none of the SQL queries for the individual rule contain any DML or DDL 
    keywords that are provided in FORBIDDEN_KEYWORDS. If it does, we pass the list of 
    all the sql queries for the rule back to sql_agent in the following format: 
    {sql_query_list: {incorrect_query: error_message}}
    """


def validate_and_execute() -> :
    """
    Check docstring of execute_sql to understand it's use.
    """
