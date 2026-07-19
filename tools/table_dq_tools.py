"""
tools/table_dq_tools.py

Tools available to the single-table DQ orchestrator agent.
"""

from langchain.tools import tool


@tool
def extract_all_metadata():
    """Extracts metadata from the given table"""
    return None


@tool
def infer_composite_pk():
    """Infers composite PK from extracted metadata"""
    return None


@tool
def infer_simple_pk():
    """Infers simple PK from extracted metadata"""
    return None


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
