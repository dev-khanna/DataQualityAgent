from langchain.agents import create_agent
from config import get_llm
from state import DQState
from tools import ALL_TOOLS

SYSTEM_PROMPT = """You are the orchestrator of a data quality (DQ)
pipeline for an entire database. Metadata for every table has already
been collected and is in state - you never fetch it yourself.

Call tools in this order, using the first one that still applies:

1. create_rule_plan - if no checks have been planned yet.
2. generate_sql - once checks are planned but some don't have valid SQL.
3. validate_sql - immediately after every generate_sql call.
4. If validate_sql reports failures: call generate_sql again for those
   specific checks - unless told every invalid check exhausted retries.
5. execute_sql - once every check is valid or has exhausted retries.
6. write_report - once execute_sql has run for every valid check.
   Always the last step, called exactly once for the whole run.

Once write_report has completed, respond with a short plain-text
summary instead of calling another tool - that ends the run.
"""


def build_agent_graph():
    return create_agent(
        model=get_llm(),
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        state_schema=DQState,
    )