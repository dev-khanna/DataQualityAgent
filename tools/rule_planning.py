"""
tools/rule_planning.py

Agentic rule planning. Gives the LLM the table's full profiled metadata
plus a generic set of principles for deriving DQ checks from it (see
RULE_PLAN_SYSTEM_PROMPT), and asks it to propose the full rule list.
Mirrors tools/pk_inference.py's pattern exactly: one structured-output
LLM call, no retrieval involved.
"""

import json

from langchain_core.messages import SystemMessage, HumanMessage

from llm import gemini_model
from prompts import RULE_PLAN_SYSTEM_PROMPT
from schemas import RulePlan


def generate_rule_plan(metadata: dict) -> RulePlan:
    structured_model = gemini_model.with_structured_output(RulePlan)
    messages = [
        SystemMessage(content=RULE_PLAN_SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(metadata, default=str)),
    ]
    return structured_model.invoke(messages)
