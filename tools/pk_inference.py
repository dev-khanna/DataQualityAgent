"""
tools/pk_inference.py

Agentic PK inference. Each function here makes one self-contained LLM
call using generic PK-selection principles - the model reasons over the
profiled metadata it's given. No table names or per-table business rules
are hardcoded here; the same two prompts are used for every table.
"""

import json

from langchain_core.messages import SystemMessage, HumanMessage

from llm import gemini_model
from prompts import SIMPLE_PK_SYSTEM_PROMPT, COMPOSITE_PK_SYSTEM_PROMPT
from schemas import PKInferenceResult


def _invoke_pk_inference(system_prompt: str, metadata: dict) -> PKInferenceResult:
    structured_model = gemini_model.with_structured_output(PKInferenceResult)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=json.dumps(metadata, default=str)),
    ]
    return structured_model.invoke(messages)


def infer_simple_pk(metadata: dict) -> PKInferenceResult:
    """Chooses the best single-column Primary Key out of metadata's
    candidate_keys."""
    return _invoke_pk_inference(SIMPLE_PK_SYSTEM_PROMPT, metadata)


def infer_composite_pk(metadata: dict) -> PKInferenceResult:
    """Proposes a composite (multi-column) Primary Key for tables where
    no single column is unique on its own."""
    return _invoke_pk_inference(COMPOSITE_PK_SYSTEM_PROMPT, metadata)
