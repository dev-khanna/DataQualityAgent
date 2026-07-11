"""
Orchestrator: the agent loop.

Wires the LLM to the toolbox in tools/__init__.py and builds the small
LangGraph loop: agent node picks a tool -> tool node runs it (tools
return Command objects that update DQState and append a ToolMessage) ->
back to agent node -> repeat, until the orchestrator responds without
calling a tool.

Retries and the "give up after MAX_RETRIES" rule are enforced inside
generate_sql itself (tools/sql_tools.py), not here - the orchestrator
only ever sees tools that are legal to call; it doesn't get a chance to
override a tool's own precondition check.
"""

from langchain.agents import create_agent
from config import get_llm
from state import DQState
from tools import ALL_TOOLS

SYSTEM_PROMPT = """You are the orchestrator of a data quality (DQ) pipeline
for a single table. You never touch the database directly - you only
call the tools available to you, one at a time, and read their results.

Call tools in this order, using the first one that still applies:

1. extract_database_metadata - if metadata hasn't been collected yet.
2. create_rule_plan - once metadata exists but no checks are planned.
3. generate_sql - once checks are planned but SQL hasn't been written
   (or a validation attempt just failed and needs fixing).
4. validate_sql - immediately after every generate_sql call.
5. If validate_sql reports failures: call generate_sql again to retry -
   unless it tells you the retry limit has been reached, in which case
   skip straight to write_report.
6. execute_sql - once validate_sql has passed.
7. write_report - once execute_sql has run, or once you've been told to
   give up after exhausting retries. Always the last step.

Once write_report has completed, respond with a short plain-text summary
instead of calling another tool - that ends this table's run.
"""


def build_agent_graph():
    return create_agent(
        model=get_llm(),
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        state_schema=DQState,
    )