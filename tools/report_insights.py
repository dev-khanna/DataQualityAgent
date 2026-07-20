"""
tools/report_insights.py

Agentic insight generation. Given every FAILED rule's executed result for
one table (write_report filters out passing checks before calling this),
asks the LLM for one short, plain-language takeaway per issue in a single
batched call - grounded in the actual violation data, not table-specific
hardcoded logic.
"""

import json

from langchain_core.messages import SystemMessage, HumanMessage

from llm import gemini_model
from prompts import REPORT_INSIGHT_SYSTEM_PROMPT
from schemas import ReportInsights


def generate_insights(results: list[dict]) -> dict[str, str]:
    """Returns a {rule_name: insight} map, one entry per result."""
    if not results:
        return {}

    structured_model = gemini_model.with_structured_output(ReportInsights)
    messages = [
        SystemMessage(content=REPORT_INSIGHT_SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(results, default=str)),
    ]
    response = structured_model.invoke(messages)
    return {item.rule_name: item.insight for item in response.insights}
