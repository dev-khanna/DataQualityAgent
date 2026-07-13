"""
The orchestrator's entire toolbox. Metadata extraction is no longer
here - it's collected once, deterministically, before the agent loop
starts (see main.py + tools/database_tools.py).
"""

from tools.report_tools import write_report
from tools.rule_tools import create_rule_plan
from tools.sql_tools import execute_sql, generate_sql, validate_sql

ALL_TOOLS = [
    create_rule_plan,
    generate_sql,
    validate_sql,
    execute_sql,
    write_report,
]