from langchain.agents import create_agent
from config import get_llm
from state import DQState, TableMetadata, initial_state_for_run
from tools import ALL_TOOLS
from tools.report_tools import read_report_from_disk

SYSTEM_PROMPT = """<role>
You are the orchestrator of a data quality (DQ) pipeline. Each time you
run, you are working on exactly ONE table. That table's metadata has
already been collected and is in state under metadata_by_table - it
will contain a single entry. You never fetch metadata yourself.
</role>

<context>
Other tables in this database may already have been checked in earlier,
separate runs (or will be, in later ones) - their results are already
part of the shared report on disk. Your write_report call appends this
table's results to that running total; it does not start a new report
and it does not need to know about any other table.
</context>

<workflow>
Call tools in this order, using the first one that still applies:

1. create_rule_plan - if no checks have been planned yet for this table.
2. generate_sql - once checks are planned but some don't have valid SQL.
3. validate_sql - immediately after every generate_sql call.
4. If validate_sql reports failures: call generate_sql again for those
   specific checks - unless told every invalid check has exhausted
   retries.
5. execute_sql - once every check is valid or has exhausted retries.
6. write_report - once execute_sql has run for every valid check.
   Always the last step, called exactly once for this table.
</workflow>

<stop_condition>
Once write_report has completed, respond with a short plain-text
summary instead of calling another tool - that ends this table's run.
</stop_condition>
"""


def build_agent_graph():
    return create_agent(
        model=get_llm(),
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        state_schema=DQState,
    )


def run_single_table_detection(table: str, table_metadata: TableMetadata) -> None:
    """Entry point for the single-table DQ branch (the 'single table DQ
    issues detector' box in the V2 architecture) - run ONCE PER TABLE.
    main.py calls this in a loop, once per table, instead of handing
    every table to a single invoke() call - each table gets its own
    fresh agent run and its own isolated state, so one table's
    check-planning/SQL-retry context never bleeds into another's.

    Before building state, this reads whatever has already been written
    to disk (from earlier tables in this run) and seeds the new state
    with it, so this table's write_report call appends to the running
    total instead of overwriting it.
    """
    app = build_agent_graph()
    existing_report = read_report_from_disk()
    state = initial_state_for_run([table], {table: table_metadata}, dq_report=existing_report)
    try:
        app.invoke(state, config={"recursion_limit": 300})
    except Exception as e:
        print(f"!! Single-table DQ run failed for '{table}': {e}")