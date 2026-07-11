"""
Orchestrator agent.

This is the supervisor: the only node that decides which worker runs
next. Workers never call each other - they always return here, and this
node decides where to go from there.

Two things are handled deterministically, without an LLM call, because
they are bookkeeping rather than judgment calls:

  1. Moving on to the next table once report_writer has run for the
     current one.
  2. Enforcing the hard MAX_RETRIES cap, as a safety net in case the LLM
     ever tries to retry past it.

Everything else - which of the six workers should run next, and whether
a failed validation should be retried - is a real decision, made by the
LLM on every call.
"""

from typing import Literal, TypedDict

from config import MAX_RETRIES, get_llm
from state import DQState

SYSTEM_PROMPT = """You are the orchestrator of a data quality (DQ) pipeline.

You never touch the database yourself. Your only job is to look at the
current state of the pipeline for the table being processed right now,
and decide which agent should run next.

Decide using these rules, in order. Use the first rule that applies:

1. If metadata has not been collected yet -> database_intelligence
2. Else if DQ checks have not been planned yet -> rule_creator
3. Else if SQL has not been generated yet -> sql_generator
4. Else if the SQL has been generated but not validated yet (no
   validation errors recorded, and it has not passed validation either)
   -> sql_validator
5. Else if the last validation attempt failed (there are validation
   errors):
   - if retry_count is below {max_retries} -> sql_generator, so it can
     fix just the checks that failed
   - otherwise -> report_writer, to record the failure and give up on
     executing this table
6. Else if validation passed but the SQL has not been executed yet ->
   sql_executor
7. Else (validation passed and the SQL has already been executed) ->
   report_writer

Only ever choose one of the six agents named above. Never invent a new
action.
"""


class OrchestratorDecision(TypedDict):
    next_agent: Literal[
        "database_intelligence",
        "rule_creator",
        "sql_generator",
        "sql_validator",
        "sql_executor",
        "report_writer",
    ]
    reason: str


def _describe_state(state: DQState) -> str:
    """Plain-text summary of where we are, for the LLM to reason over."""
    return "\n".join([
        f"Current table: {state['current_table']}",
        f"Tables still waiting after this one: {state['tables']}",
        f"Metadata collected: {state['metadata'] is not None}",
        f"DQ checks planned: {state['planned_checks'] is not None}",
        f"SQL generated: {state['compiled_rules'] is not None}",
        f"SQL validated and passed: {state['sql_valid']}",
        f"Validation errors: {state['validation_errors']}",
        f"Retry count: {state['retry_count']} / {MAX_RETRIES}",
        f"SQL executed: {len(state['execution_results']) > 0}",
    ])


def _reset_for_next_table(state: DQState) -> dict:
    """Pop the next table off the queue and clear out per-table fields.
    If there's nothing left to process, signal that the run is finished."""
    remaining = state["tables"]
    if not remaining:
        return {"next_agent": "finished"}

    next_table, *rest = remaining
    return {
        "tables": rest,
        "current_table": next_table,
        "metadata": None,
        "planned_checks": None,
        "compiled_rules": None,
        "validation_errors": [],
        "sql_valid": False,
        "execution_results": [],
        "retry_count": 0,
        "next_agent": "database_intelligence",
    }


def orchestrator_node(state: DQState) -> dict:
    # Mechanical transition: report_writer is always the last step for a
    # table, so once it has run there's nothing to decide - just advance.
    if state["next_agent"] == "report_writer":
        return _reset_for_next_table(state)

    llm = get_llm().with_structured_output(OrchestratorDecision)
    system = SYSTEM_PROMPT.format(max_retries=MAX_RETRIES)
    decision = llm.invoke([
        {"role": "system", "content": system},
        {"role": "user", "content": _describe_state(state)},
    ])

    next_agent = decision["next_agent"]

    # Hard safety net: never allow more than MAX_RETRIES regenerations,
    # no matter what the LLM decided.
    if next_agent == "sql_generator" and state["retry_count"] >= MAX_RETRIES:
        next_agent = "report_writer"

    return {"next_agent": next_agent}