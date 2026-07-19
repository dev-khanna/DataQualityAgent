"""
schemas.py

Pydantic schemas for any LLM call that needs structured output (e.g. PK
inference, rule planning, report entries). Keep every schema to
BaseModel + Field only - no custom validators, no extra config classes.

Empty for now. Schemas get added here as each tool's LLM call is
implemented in a later step.
"""

from pydantic import BaseModel, Field
