"""
schemas.py

Pydantic schemas for any LLM call that needs structured output (e.g. PK
inference, rule planning, report entries). Keep every schema to
BaseModel + Field only - no custom validators, no extra config classes.

All of these can be edited but keep it simple, minimal and easy to understand.
"""

from typing import List

from pydantic import BaseModel, Field


class PKInferenceResult(BaseModel):
    """Structured output for both infer_simple_pk and infer_composite_pk.
    A simple PK is just a one-element pk_columns list."""

    pk_columns: List[str] = Field(
        description="Ordered list of column name(s) that make up the inferred primary key."
    )
    rationale: str = Field(
        description="Short explanation of why these column(s) were chosen as the primary key."
    )


class DQRule(BaseModel):
    """One data quality check."""

    rule_name: str = Field(description="Short, unique name for this check.")
    description: str = Field(
        description="What the check verifies and which column(s) it applies to, precise "
        "enough that a SQL-writing step could act on it directly."
    )


class RulePlan(BaseModel):
    """Structured output for tools.dq_chain.plan_rules."""

    rules: List[DQRule] = Field(description="Every data quality check to run for this table.")


class RuleInsight(BaseModel):
    """One rule's plain-language takeaway, generated as it's checked off."""

    rule_name: str = Field(description="Which rule this insight is for - must match a rule_name you were given.")
    insight: str = Field(description="A one to two sentence, plain-language takeaway from that rule's result.")


class ReportInsights(BaseModel):
    """Structured output for the insight-generation call."""

    insights: List[RuleInsight] = Field(description="One insight per rule bundle you were given.")


