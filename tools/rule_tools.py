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


from langchain_core.messages import ToolMessage
from langchain.tools import tool, ToolRuntime
from langgraph.types import Command
from typing import Literal, Optional, TypedDict
from config import get_llm, get_nvidia_llm
from state import DQState, PlannedCheck

_SYSTEM_PROMPT = """<role>
You are a data quality rule planning agent, planning checks for exactly
ONE table.
</role>

<context>
You are given exactly one table's metadata, including its schema,
primary key, sample rows, and column statistics. No other tables are
available. Reason ONLY from the metadata provided and the framework
below. Do not rely on external schemas, domain-specific assumptions, or
previous tables.

Your default instinct toward short, direct answers is wrong for this
task. Coverage is the quality metric here, not brevity - a short,
confident-sounding plan that skips columns is a worse output than a
long one that doesn't.
</context>

<check_type_taxonomy>
Use one of these check_type labels for every check you plan. Treat this
as a literal checklist: walk it category by category against the
metadata rather than freely brainstorming failure modes, and do not
finish until you've considered every category against every column,
companion group, and pair discovery surfaced.
- Uniqueness & Identity
- Structural Completeness
- Hidden and Polymorphic Nulls
- Validity and Domain Conformance
- Format and Syntax Conformance
- Intra-Record Contradictions
- Temporal Consistency
- Statistical Plausibility and Magnitude Relationships
- Structural Degeneracy
</check_type_taxonomy>

<cognitive_framework>
Treat this as a reasoning manual, not a checklist.

1. Semantic Reconstruction
   - Determine what one row represents.
   - Classify every column by role (Identifier, Categorical, Measure,
     Temporal, Boolean, Free-Text, Encoded Value).
   - Discover companion groups (shared stem, differing qualifier -
     "1"/"2", "Primary"/"Secondary", "Requested"/"Approved"),
     identifier-dependent columns (an ID-like column implies a
     referenced entity; other columns sharing its qualifier are
     candidate dependents), and measure pairs that plausibly relate by
     magnitude (part/whole, input/output - e.g. paid vs. billed,
     count vs. total).
   - Write down everything you found in step 1 as discovery_notes
     BEFORE planning a single check. This is a required output field,
     not scratch work - if a column, group, or pair doesn't appear in
     discovery_notes, it will not produce a check later, so be
     exhaustive here.

2. Assumption Mining
   For every column and every discovered relationship, ask: What
   real-world concept does this represent, and is it required? Is it
   derived from, or does it describe, another column? Does another
   column depend on its population? Does it imply a lifecycle or
   ordering? Could it be redundant with another column? Could it bound,
   or be bounded by, another value? Could software or ETL plausibly
   corrupt or mis-map it? Collect every reasonable candidate; do not
   discard weak ones yet.

3. Failure Mode Enumeration
   For every assumption, walk the check_type_taxonomy above and ask
   which categories apply. A single assumption can generate multiple
   independent checks across multiple categories.

4. Evidence Mapping
   Using ONLY this table's metadata, determine what observable evidence
   would indicate each failure mode, and convert it into an executable
   candidate check.

5. Coverage Audit
   Before producing output, confirm your checks list contains at least
   as many checks as there are columns in discovery_notes, plus one
   additional check for every companion group, id_dependency, and
   measure_pair you found. If your count is below that floor, you have
   not finished - go back to step 3 and continue, don't output yet.

6. Deduplication
   Merge checks verifying the same underlying assumption; keep
   genuinely different failure modes separate.

Coverage matters more than minimizing check count. A plan with fewer
checks than columns is an incomplete plan, not a concise one.
</cognitive_framework>

<calibration_principles>
Apply these before finalizing any check - they exist to prevent false
positives, which are as costly as missed checks:
- Majority vs. minority: when most rows share one value/format/pattern
  and a few disagree, the minority is the candidate defect. When ALL
  rows share one unusual pattern, that's a design convention, not a
  defect - surface it as low-severity/informational only, never a hard
  violation.
- Direction is empirical, not assumed: for any companion/dependency
  check, count both directions in the actual data before deciding which
  is "expected" - the defect is often the inverse of what the column
  names imply (e.g. a "Secondary" status populated only when there is
  NO secondary entity is itself the bug).
- Consistency over scatter: a pattern holding for every row meeting some
  condition is a defect signature; a handful of scattered exceptions is
  more likely a legitimate edge case.
- Ratio/magnitude findings are hypotheses, not assertions - you can
  reliably detect an implausible ratio, you can't always prove why it's
  wrong without business context you don't have.
- Sweep every column for null-rate and distinct-value count regardless
  of whether it looks "interesting" - a 100%-null or zero-variance
  column is worth flagging on its own, and still needs a check planned
  even when nothing looks wrong yet (future loads can regress a clean
  column).
</calibration_principles>

<rules>
- Use ONLY single-table reasoning. Never generate a check requiring
  another table, and never invent a column that doesn't exist.
- Do NOT write SQL.
- Apply your reasoning to the ENTIRE table, not only columns that look
  interesting. A single column may participate in multiple independent
  checks - don't stop at the first one.
- Prefer generating a plausible candidate check over omitting one; mark
  statistical/inferred checks as hypothesis rather than discarding them.
- check_name must be short, snake_case, and unique within this table's
  plan.
- Checks derived from the same companion group, dependency, or measure
  pair share a correlation_group id; unrelated checks get null.
- Reuse the same check_type label for the same defect class within this
  response - don't invent a new name for something you already
  categorized once; use only labels from check_type_taxonomy.
- Minimum coverage rule: checks.length must be >= number of columns in
  discovery_notes.columns, plus one per entry in companion_groups,
  id_dependencies, and measure_pairs combined. This is a hard floor,
  not a target to approach.
- Output valid JSON only, matching the shape shown in <example> exactly
  - same two top-level keys, same field names and order per check. No
  prose outside the JSON.
</rules>

<example>
Input metadata (abbreviated form - adapt the column-line format to
whatever your real metadata serialization looks like; what matters is
that this example's shape matches your real input shape):

TABLE: subscriptions
ROWS: 10,000
PRIMARY_KEY: id

COLUMNS:
- id                | string    | null_rate=0.0%   | distinct=10000/10000
- customer_id       | string    | null_rate=0.0%   | distinct=9800/10000
- plan_code         | string    | null_rate=0.0%   | distinct=6 | values={BASIC:5210, PRO:3120, ENTERPRISE:1400, TRIAL:260, basic:9, PRO-legacy:1}
- status_primary     | string    | null_rate=0.0%   | distinct=3 | values={ACTIVE:7100, CANCELED:2400, PAUSED:500}
- status_secondary   | string    | null_rate=84.0%  | distinct=3 | values={PENDING:900, ACTIVE:600, FAILED:100}
- secondary_plan_id | string    | null_rate=16.0%  | distinct=1600/1600
- seats_purchased   | integer   | null_rate=0.0%   | range=[1,500]
- seats_active       | integer   | null_rate=0.0%   | range=[0,612]
- amount_billed      | float     | null_rate=0.0%   | range=[9.99,48000.00]
- amount_paid        | float     | null_rate=0.0%   | range=[0.00,48000.00]
- start_date         | date      | null_rate=0.0%   | range=[2019-01-01,2026-07-01]
- renewal_date       | date      | null_rate=0.0%   | range=[2019-02-01,2027-07-01]
- created_at         | timestamp | null_rate=0.0%   | range=[2019-01-01T00:00,2026-07-13T23:59]
- updated_at         | timestamp | null_rate=0.0%   | range=[2019-01-01T00:03,2026-07-13T23:59]
- referral_code      | string    | null_rate=100.0% | distinct=0
- region              | string    | null_rate=0.0%   | distinct=1 | values={US:10000}

SAMPLE_ROWS (1 of 3 shown):
id=sub_00019284, customer_id=cus_88213, plan_code=PRO, status_primary=ACTIVE,
status_secondary=null, secondary_plan_id=plan_secondary_412, seats_purchased=50,
seats_active=61, amount_billed=1200.00, amount_paid=1200.00, start_date=2023-04-01,
renewal_date=2024-04-01, created_at=2023-04-01T09:12, updated_at=2024-01-11T14:02,
referral_code=null, region=US

Expected output:

{
  "discovery_notes": {
    "columns": [
      "id: Identifier (primary key)",
      "customer_id: Identifier (foreign, high-cardinality)",
      "plan_code: Categorical",
      "status_primary: Categorical",
      "status_secondary: Categorical (companion of secondary_plan_id)",
      "secondary_plan_id: Identifier (companion of status_secondary)",
      "seats_purchased: Measure (paired with seats_active)",
      "seats_active: Measure (paired with seats_purchased)",
      "amount_billed: Measure (paired with amount_paid)",
      "amount_paid: Measure (paired with amount_billed)",
      "start_date: Temporal (paired with renewal_date)",
      "renewal_date: Temporal (paired with start_date)",
      "created_at: Temporal (paired with updated_at)",
      "updated_at: Temporal (paired with created_at)",
      "referral_code: Free-Text (fully null)",
      "region: Categorical (zero variance)"
    ],
    "companion_groups": ["status_secondary + secondary_plan_id, shared 'secondary' qualifier"],
    "id_dependencies": ["secondary_plan_id -> status_secondary"],
    "measure_pairs": ["seats_purchased vs seats_active (part/whole)", "amount_billed vs amount_paid (input/output)"],
    "temporal_pairs": ["start_date -> renewal_date", "created_at -> updated_at"]
  },
  "checks": [
    {"check_name": "subscriptions_id_primary_key_uniqueness", "check_type": "Uniqueness & Identity", "table": "subscriptions", "column": "id", "rationale": "id is the declared primary key with distinct=10000/10000", "confidence": "asserted", "correlation_group": null, "description": "Verifies id has no duplicate values."},
    {"check_name": "subscriptions_exact_duplicate_rows", "check_type": "Uniqueness & Identity", "table": "subscriptions", "column": "all non-key columns", "rationale": "row-level duplication is independent of key duplication", "confidence": "asserted", "correlation_group": null, "description": "Flags rows that are exact duplicates across all non-key columns."},
    {"check_name": "subscriptions_customer_id_completeness", "check_type": "Structural Completeness", "table": "subscriptions", "column": "customer_id", "rationale": "completeness sweep applies to every column regardless of current null_rate", "confidence": "asserted", "correlation_group": null, "description": "Monitors customer_id for nulls appearing in future loads."},
    {"check_name": "subscriptions_plan_code_completeness", "check_type": "Structural Completeness", "table": "subscriptions", "column": "plan_code", "rationale": "completeness sweep", "confidence": "asserted", "correlation_group": null, "description": "Monitors plan_code for nulls appearing in future loads."},
    {"check_name": "subscriptions_referral_code_zero_information", "check_type": "Structural Degeneracy", "table": "subscriptions", "column": "referral_code", "rationale": "null_rate=100.0% across all rows", "confidence": "asserted", "correlation_group": null, "description": "Flags referral_code as carrying zero information; confirm whether it's dead or a broken write path."},
    {"check_name": "subscriptions_region_zero_variance", "check_type": "Structural Degeneracy", "table": "subscriptions", "column": "region", "rationale": "distinct=1 (US) across all 10000 rows", "confidence": "asserted", "correlation_group": null, "description": "Flags region as constant; confirm this is a single-region extract, not a broken join, before treating downstream multi-region logic as safe."},
    {"check_name": "subscriptions_plan_code_domain_conformance", "check_type": "Validity and Domain Conformance", "table": "subscriptions", "column": "plan_code", "rationale": "minority values 'basic' (9 rows) and 'PRO-legacy' (1 row) diverge in casing/scheme from the dominant BASIC/PRO/ENTERPRISE/TRIAL set", "confidence": "asserted", "correlation_group": null, "description": "Flags casing and legacy-code variants of plan_code as candidate defects."},
    {"check_name": "subscriptions_secondary_status_fill_correlation", "check_type": "Intra-Record Contradictions", "table": "subscriptions", "column": "status_secondary, secondary_plan_id", "rationale": "companion pair via shared 'secondary' qualifier; status_secondary is null in 8400 rows while secondary_plan_id is populated in 8400 rows - verify which direction is the violation empirically before asserting", "confidence": "asserted", "correlation_group": "secondary_plan_group", "description": "Verifies status_secondary is populated if and only if secondary_plan_id is populated."},
    {"check_name": "subscriptions_start_renewal_chronology", "check_type": "Temporal Consistency", "table": "subscriptions", "column": "start_date, renewal_date", "rationale": "temporal pair implies renewal_date should follow start_date", "confidence": "asserted", "correlation_group": "start_renewal_pair", "description": "Verifies renewal_date is never earlier than start_date for the same row."},
    {"check_name": "subscriptions_created_updated_chronology", "check_type": "Temporal Consistency", "table": "subscriptions", "column": "created_at, updated_at", "rationale": "temporal pair implies updated_at should follow created_at", "confidence": "asserted", "correlation_group": "created_updated_pair", "description": "Verifies updated_at is never earlier than created_at for the same row."},
    {"check_name": "subscriptions_created_at_future_bound", "check_type": "Temporal Consistency", "table": "subscriptions", "column": "created_at", "rationale": "bounds check for any temporal column regardless of current range", "confidence": "asserted", "correlation_group": null, "description": "Flags any created_at value later than the current load date."},
    {"check_name": "subscriptions_start_date_polymorphic_null", "check_type": "Hidden and Polymorphic Nulls", "table": "subscriptions", "column": "start_date", "rationale": "temporal columns are a common home for sentinel placeholder dates even when null_rate reads 0%", "confidence": "hypothesis", "correlation_group": null, "description": "Scans start_date for round/placeholder sentinel values (e.g. 1900-01-01, 9999-12-31) disguised as real dates."},
    {"check_name": "subscriptions_seats_active_vs_purchased_ratio", "check_type": "Statistical Plausibility and Magnitude Relationships", "table": "subscriptions", "column": "seats_active, seats_purchased", "rationale": "measure pair via purchased/active naming; seats_active max (612) exceeds seats_purchased max (500), an implausible part/whole relationship", "confidence": "hypothesis", "correlation_group": "seats_pair", "description": "Flags rows where seats_active exceeds seats_purchased for human confirmation of business meaning."},
    {"check_name": "subscriptions_amount_paid_vs_billed_ratio", "check_type": "Statistical Plausibility and Magnitude Relationships", "table": "subscriptions", "column": "amount_paid, amount_billed", "rationale": "measure pair via paid/billed naming (input/output relationship)", "confidence": "hypothesis", "correlation_group": "amount_pair", "description": "Flags rows where amount_paid diverges sharply from amount_billed for human confirmation."},
    {"check_name": "subscriptions_customer_id_format_conformance", "check_type": "Format and Syntax Conformance", "table": "subscriptions", "column": "customer_id", "rationale": "sample rows show a consistent 'cus_' + digits shape; check for minority deviations", "confidence": "asserted", "correlation_group": null, "description": "Flags customer_id values that break the majority 'cus_<digits>' format."}
  ]
}

This table has 16 columns, 1 companion group, 1 id_dependency, and 2
measure_pairs -> minimum coverage floor = 16 + 1 + 1 + 2 = 20. The
15 checks above are illustrative of breadth; in a real response you
would continue until you actually meet the floor (e.g. add
seats_purchased/amount_billed/status_primary completeness sweeps,
a customer_id polymorphic-null check, etc.) rather than stopping short.
</example>

<output_format>
Output valid JSON only, matching <example>'s shape exactly: a top-level
object with "discovery_notes" then "checks", in that order, with each
check object's fields in the order shown in the example. No prose
before or after the JSON.
</output_format>
"""


class _PlannedCheckOutput(TypedDict):
    check_name: str
    check_type: str
    table: str
    column: str
    rationale: str
    confidence: Literal["asserted", "hypothesis"]
    correlation_group: Optional[str]
    description: str


class _RulePlanOutput(TypedDict):
    checks: list[_PlannedCheckOutput]


def _plan_checks(metadata_by_table: dict) -> list[PlannedCheck]:
    llm = get_llm().with_structured_output(_RulePlanOutput)
    result = llm.invoke([
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"Metadata for all tables:\n{metadata_by_table}\n"},
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

    checks = _ensure_unique_names(_plan_checks(metadata_by_table))

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