"""
agents/table_dq_agent.py

Builds the single-table DQ orchestrator agent - the first pipeline stage.
Runs once per table, per the workflow described in TABLE_DQ_SYSTEM_PROMPT.
"""

from langchain.agents import create_agent
from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain.agents.middleware import TodoListMiddleware

from llm import gemini_model
from prompts import TABLE_DQ_SYSTEM_PROMPT
from tools.table_dq_tools import (
    extract_all_metadata,
    create_rule_plan,
    generate_sql,
    validate_sql,
    execute_sql,
    write_report,
)

tools = [
    extract_all_metadata,
    create_rule_plan,
    generate_sql,
    validate_sql,
    execute_sql,
    write_report,
]

table_dq_agent = create_agent(
    model=gemini_model,
    tools=tools,
    system_prompt=TABLE_DQ_SYSTEM_PROMPT,
    middleware=[FilesystemMiddleware(), TodoListMiddleware()],
)