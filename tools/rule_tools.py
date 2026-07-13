"""
Rule Creator tool.

Exposes create_rule_plan. Makes ONE LLM call for the single table this
run is scoped to (orchestrator.run_single_table_detection invokes the
whole graph once per table, so metadata_by_table here will contain
exactly one entry). This ONLY plans single-table checks - cross-table
checks (e.g. referential integrity) are intentionally deferred to
cross_table.py, but related_table already exists on
PlannedCheck/CompiledRule (see state.py) so adding them later is a
prompt/logic change here, not a state migration.
"""

from typing import TypedDict

from langchain_core.messages import ToolMessage
from langchain.tools import tool, ToolRuntime
from langgraph.types import Command

from config import get_llm, get_nvidia_llm
from state import DQState, PlannedCheck
from utils.helpers import read_knowledge_base

_SYSTEM_PROMPT = """<role>
You are a data quality rule planning agent, planning checks for exactly
ONE table.
</role>

<context>
You are given that table's metadata (schema, primary key, sample rows,
column stats) and a knowledge base describing single-table data quality
checks, organized as defect categories with generic detection heuristics
rather than per-column rules. No other table's metadata is available to
you in this run, by design - reason using this table's own structure and
contents only.
</context>

<cognitive_framework>
Before planning any checks, run the knowledge base's
column_relationship_discovery protocol against the metadata you were
given, and use its output as the input to every category below - do not
plan checks by scanning column names ad hoc.
1. Build the map: classify every column's role (Identifier, Categorical,
   Measure, Temporal, Free-Text, Boolean); group companion columns
   (shared stem, differing qualifier like "1"/"2" or "Primary"/
   "Secondary"); link ID-like columns to their dependent columns; pair
   up measures that plausibly relate by magnitude (part/whole,
   input/output).
2. Walk every category in the knowledge base against this map, not
   against memory of past tables - a category applies whenever its
   generic_signal matches something in the map, regardless of whether
   this exact defect has been seen before.
3. For every companion group and ID-to-dependent mapping found, plan an
   Intra-Record Contradictions check verifying whichever fill-pattern
   (co-presence, mutual exclusivity, directional dependency) the data's
   majority actually follows - determine the expected direction from
   the data itself, not from the column names, since the defect is
   often the inverse of what the names imply.
4. Always plan the generic sweeps (Structural Completeness and
   Structural Degeneracy) across every column in the metadata, not only
   columns called out by name - a 100%-null column or a zero-variance
   column is worth flagging on its own even with no other context.
5. For any measure pair surfaced by the map, plan a magnitude/ratio
   plausibility check and mark it per the knowledge base's hypothesis
   guardrail rather than asserting a root cause.
</cognitive_framework>

<rules>
- Use ONLY the knowledge base's single-table checks. Do NOT plan any
  check that requires comparing values across two tables (e.g. do not
  attempt referential integrity / foreign key checks) - that is a
  separate cross-table detector's job, not yours.
- Do NOT wait to be told which columns to check. Apply every category's
  generic_signal against the full column list; coverage should be
  exhaustive, not limited to columns that look obviously interesting.
- Do NOT write any SQL. Only plan checks against columns that actually
  exist in the metadata you were given.
- check_name must be short, snake_case, and unique among the checks you
  plan in this call (prefixing with the table name is a safe default).
- When two or more checks you're planning stem from the same companion
  group or ID-dependent mapping (per the discovery map), assign them
  the same correlation_group id so a downstream step can later verify
  whether their violations land on the same rows. Do not attempt that
  row-level comparison yourself - you plan checks, you don't execute
  them, and Root-Cause Clustering itself is out of scope for your
  check_type output; your job ends at tagging the group.
- Statistical/magnitude checks (ratio plausibility, outlier bounds,
  minority-domain values) must be marked confidence: hypothesis rather
  than confidence: asserted, per the knowledge base's guardrail - you
  can detect an implausible pattern reliably; you cannot always assert
  its cause.
</rules>

<output_format>
For each check, provide:
- check_name: short, snake_case, unique within this table's plan.
- check_type: a category name from the knowledge base, verbatim.
- table: the table this check belongs to.
- column: the column(s) the check applies to - a comma-separated list
  for any cross-column check (Intra-Record Contradictions, Temporal
  Consistency, Statistical Plausibility).
- rationale: one sentence naming the generic_signal that triggered this
  check (e.g. "companion group detected via shared 'Secondary'
  qualifier", "100% null sweep", "measure pair via paid/revenue
  naming") - the signal that applies to THIS table's columns, not a
  general justification for the check type.
- confidence: asserted | hypothesis - hypothesis for any statistical,
  ratio, or minority-domain check per the knowledge base's guardrail,
  asserted otherwise.
- correlation_group: an id shared by checks derived from the same
  companion group or ID-dependent mapping, or null if this check
  stands alone.
- description: one sentence describing what the check verifies.
</output_format>
"""


class _PlannedCheckOutput(TypedDict):
    check_name: str
    check_type: str
    table: str
    column: str
    description: str


class _RulePlanOutput(TypedDict):
    checks: list[_PlannedCheckOutput]


def _plan_checks(metadata_by_table: dict, knowledge_base: str) -> list[PlannedCheck]:
    llm = get_llm().with_structured_output(_RulePlanOutput)
    result = llm.invoke([
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Knowledge base:\n{knowledge_base}\n\n"
            f"Metadata for all tables:\n{metadata_by_table}\n"
        )},
    ])
    return [{**c, "related_table": None} for c in result["checks"]]


def _ensure_unique_names(checks: list[PlannedCheck]) -> list[PlannedCheck]:
    """Deterministic safety net: the LLM was told to keep names globally
    unique, but nothing enforces that. A collision here would corrupt
    per-check retry/status tracking downstream, so fix it in code
    rather than trusting the prompt."""
    seen: dict[str, int] = {}
    deduped = []
    for c in checks:
        name = c["check_name"]
        if name in seen:
            seen[name] += 1
            c = {**c, "check_name": f"{name}_{seen[name]}"}
        else:
            seen[name] = 0
        deduped.append(c)
    return deduped


@tool
def create_rule_plan(runtime: ToolRuntime[None, DQState]) -> Command:
    """Decide which data quality checks should exist for this table,
    based on this table's own metadata. Call once, before any SQL is
    written."""
    metadata_by_table = runtime.state["metadata_by_table"]

    if not metadata_by_table:
        return Command(update={
            "messages": [ToolMessage(
                content="Cannot plan checks: no table metadata is available for this run.",
                tool_call_id=runtime.tool_call_id,
            )],
        })

    knowledge_base = read_knowledge_base()
    checks = _ensure_unique_names(_plan_checks(metadata_by_table, knowledge_base))

    return Command(update={
        "planned_checks": checks,
        "messages": [ToolMessage(
            content=(
                f"Planned {len(checks)} check(s) across {len(metadata_by_table)} "
                f"table(s): {[c['check_name'] for c in checks]}."
            ),
            tool_call_id=runtime.tool_call_id,
        )],
    })