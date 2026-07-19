"""
schemas.py

Pydantic schemas for any LLM call that needs structured output (e.g. PK
inference, rule planning, report entries). Keep every schema to
BaseModel + Field only - no custom validators, no extra config classes.
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
