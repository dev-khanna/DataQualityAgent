"""
agents/cross_table_dq_agent.py

Builds the cross-table DQ orchestrator agent - the second pipeline stage,
responsible for issues that span multiple tables (e.g. foreign key /
referential integrity checks). Runs once, after every table has been
checked individually by table_dq_agent.

Left blank for now - implemented in a later step.
"""

# you dump schema + a few sample rows + which columns are unique-ish for all tables into the llm
# you ask it: "look at these tables, tell me which columns in one table probably point to another 
# table's primary key — even if the name doesn't say _id, just use column names, sample values, and
# common sense (like a column called PATIENT in a table about events, probably points to the 
# patients table)"
# llm gives you back a list of guesses, like encounters.PATIENT → patients.Id, with a confidence 
# label like "high" or "medium"
# now here's the part to get right: that confidence label is just the llm's opinion, it's not proof.
# so for every guess it gives you, you run this same kind of query, swapping in the actual 
# table/column names:

# SELECT COUNT(*), COUNT(*) FILTER (WHERE b."Id" IS NULL)
# FROM "encounters" a LEFT JOIN "patients" b
# ON a."PATIENT" = b."Id"
# WHERE a."PATIENT" IS NOT NULL

# this query returns a number: how many rows didn't find a match
# and that number can mean one of three totally different things:
# if say less than 25 percent of the rows matched, its not a real relationship. 
# whereas if 100% matched, then theres a relationship but no dq issue.
# and if its between 25 and 100 then theres the dq issue that is orphaned foreign keys.

# during this process we collect: {from_table, from_column, to_table, to_column}
# this will be used for the cross table checks by passing certain table/columnwise metadata and the
# FK relationships dictionary to an LLM, where it creates rules just like our single table DQ checker.
# Once, thats done we follow the same pipeline of sql generation, validation, execution and writing
# the report. 

# which metadata must we pass?
# {from_table, from_column, to_table, to_column}, orphan_count
# schema, column_stats, primary_key, sample_rows

cross_table_dq_agent = None
