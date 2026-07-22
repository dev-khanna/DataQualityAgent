"""
tools/rule_planning.py

Deterministic LLM call. It inputs the table's complete profiled metadata
and a generic set of principles for deriving DQ checks from it 
(RULE_PLAN_SYSTEM_PROMPT), and asks it to come up with a bunch of rules 
that may indicate possible data quality issues that may exist due to a column
or the relationship between multiple columns within a table. As and when it
comes up with rules, they must populate todo_list.md. 
"""

import json

from langchain_core.messages import SystemMessage, HumanMessage

from llm import gemini_model
from prompts import RULE_PLAN_SYSTEM_PROMPT
from schemas import RulePlan


def generate_rule_plan(metadata: dict) -> :
    structured_model = gemini_model.with_structured_output(RulePlan)
    messages = [
        SystemMessage(content=RULE_PLAN_SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(metadata, default=str)),
    ]
    #complete the rest of it
