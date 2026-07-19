from langchain.agents import create_agent
from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain.agents.middleware import TodoListMiddleware

from llm import gemini_model
from prompts import CROSS_TABLE_DQ_SYSTEM_PROMPT
from tools.table_dq_tools import (
    extract_all_metadata,
    infer_composite_pk,
    infer_simple_pk,
    create_rule_plan,
    generate_sql,
    validate_sql,
    execute_sql,
    write_report,
)

tools = [
    extract_all_metadata,
    infer_composite_pk,
    infer_simple_pk,
    create_rule_plan,
    generate_sql,
    validate_sql,
    execute_sql,
    write_report,
]

cross_table_dq_agent = create_agent(
    model=gemini_model,
    tools=tools,
    system_prompt=CROSS_TABLE_DQ_SYSTEM_PROMPT,
    middleware=[FilesystemMiddleware(), TodoListMiddleware()],
)