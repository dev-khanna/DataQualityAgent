"""
The orchestrator's entire toolbox. This is what main.py hands to the
graph - the orchestrator can see these six functions and nothing else.
Each tool's own docstring is the only description the LLM gets; the
real implementation (private helpers, any internal LLM calls) lives in
that tool's own module and is never visible up here.
"""

from tools.database_tools import extract_database_metadata
from tools.report_tools import write_report
from tools.rule_tools import create_rule_plan
from tools.sql_tools import execute_sql, generate_sql, validate_sql

ALL_TOOLS = [
    extract_database_metadata,
    create_rule_plan,
    generate_sql,
    validate_sql,
    execute_sql,
    write_report,
]