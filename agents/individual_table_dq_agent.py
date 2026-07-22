"""
agents/individual_table_dq_agent.py

Builds the single-table DQ pipeline which runs the full pipeline for 
each table, one at a time:

1. Metadata extraction + PK inference, then rule planning. These are
   chained together as plan function calls (tools/chain_before_sql_agent.py).
   Neither of them is a tool the sql_agent (react agent) can call.

2. The resulting rules are written to todo_list.md, where new rules are 
   appended for each table that's processed.  
   Each rule is appended in the todo list in the form of a dictionary in
   the following format:  {{rule_name: rule_description}: status}
   As per my understanding, the todo list automatically assigns the status.

3. todo_list.md is then passed onto our ReAct agent (sql_agent), which is 
   also provided with exactly two tools (execute_sql, append_result) and
   TodoListMiddleware. This todo list will be edited, followed and 
   maintained as per the requirements of sql_agent.
   For every rule it sees in todo_list.md, sql_agent generates a set of 
   appropriate SQL queries. Once it thinks that the set of SQL queries 
   satisfactorily check for the rule, it passes them to execute_sql, where 
   the queries are validated and executed. If a query fails to validate,
   it is sent along with the error back to sql_agent where it tries to 
   regenerate the correct query based on the error returned. Once, the set
   of queries pass validation, they are executed by the same tool successfully.
   Once a the SQL queries for a rule in the todo list are all executed, iff
   a data quality issue is found, it is appended to our dq report using the 
   append_result tool. After this, we move on to the next rule to check.
"""

from langchain_core.messages import HumanMessage
from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware

from llm import gemini_model
from prompts import INDIVIDUAL_TABLE_DQ_SYSTEM_PROMPT
from tools.chain_before_sql_agent import extract_metadata, plan_rules
from tools.sql_agent_tools import execute_sql, append_result

tools = [execute_sql, append_result]

individual_table_dq_agent = create_agent(
    model=gemini_model,
    tools=tools,
    system_prompt=INDIVIDUAL_TABLE_DQ_SYSTEM_PROMPT,
    middleware=[TodoListMiddleware()],
)


def _format_schema(schema: list[dict]) -> str:
    """Renders the profiled schema as plain 'column_name (column_type)'
    lines - the exact column names the agent must use in every query."""
    return "\n".join(f"- {col['column_name']} ({col['column_type']})" for col in schema)


def _format_rules(rules: list) -> str:
    """Renders the planned rules as 'rule_name: description' lines - this
    table's already-populated Todo List."""
    return "\n".join(f"- {rule.rule_name}: {rule.description}" for rule in rules)


def run_individual_table_dq_check(table_name: str) -> dict:
    """
    Runs the full single-table DQ pipeline for one table. 
    Check module docstring for the three stages.
    """
    metadata = extract_metadata(table_name)
    rule_plan = plan_rules(metadata)

    first_message = HumanMessage(
        content=(
            f"Table: {table_name}\n\n"
            f"Schema (use these exact column names and types in every query):\n"
            f"{_format_schema(metadata['schema'])}\n\n"
            f"Your Todo List for this table - one item per rule, already "
            f"planned for you:\n"
            f"{_format_rules(rule_plan.rules)}"
        )
    )

    return individual_table_dq_agent.invoke({"messages": [first_message]})
