"""
tools/sql_generation.py

Agentic SQL generation. Given one DQ rule, re-fetches the table's real
schema (deterministically - never trusts the orchestrator to relay column
names correctly) and asks the LLM to write a single "violations query"
for it. Supports an optional previous_error so a retry after a failed
validate_sql actually fixes the specific problem instead of re-rolling.
"""

import json

from langchain_core.messages import SystemMessage, HumanMessage

from llm import gemini_model
from prompts import GENERATE_SQL_SYSTEM_PROMPT
from schemas import GeneratedSQL
from tools.metadata_profiling import get_schema


def generate_sql_for_rule(table_name: str, rule: dict, previous_error: str = None) -> GeneratedSQL:
    payload = {
        "table_name": table_name,
        "schema": get_schema(table_name),
        "rule": rule,
    }
    if previous_error:
        payload["previous_attempt_error"] = previous_error

    structured_model = gemini_model.with_structured_output(GeneratedSQL)
    messages = [
        SystemMessage(content=GENERATE_SQL_SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(payload, default=str)),
    ]
    return structured_model.invoke(messages)