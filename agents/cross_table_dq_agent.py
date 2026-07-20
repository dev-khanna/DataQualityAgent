"""
agents/cross_table_dq_agent.py

Builds the cross-table DQ orchestrator agent - the second pipeline stage,
responsible for issues that span multiple tables (e.g. foreign key /
referential integrity checks). Runs once, after every table has been
checked individually by table_dq_agent.

Left blank for now - implemented in a later step.
"""

cross_table_dq_agent = None
