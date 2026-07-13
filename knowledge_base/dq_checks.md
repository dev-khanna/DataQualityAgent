_KNOWLEDGE_BASE = """<knowledge_base version="2.0" scope="single_table">

<purpose>
This KB defines classes of data quality defects, not instances of them. Each category
gives the planning agent a generic SIGNAL (how to notice the pattern from schema/stats
alone, without a human naming the column), a HEURISTIC (the general reasoning rule), and
a CHECK TEMPLATE (a parameterized check shape, not a literal rule). The agent should be
able to derive a correct check for a table it has never seen, in a domain it has never
seen, using only this reasoning - the same way a rule for "check all foreign-key-shaped
columns for fill correlation with their dependent fields" generalizes across insurance
claims, e-commerce orders, or logistics shipments without modification.

Category names below are canonical `check_type` values for the planning agent's
output_format.
</purpose>

<how_to_use>
Run <discovery_protocol> first - it produces a map of column roles and column groups.
Every category below consumes that map as its input rather than looking at raw column
names case-by-case. After all per-category checks are planned, run
<category name="Root-Cause Clustering"> as a final pass over the *planned checks
themselves*, not the columns, to merge checks that are likely the same underlying defect.
</how_to_use>

<discovery_protocol name="column_relationship_discovery">
  <goal>Build a semantic map of the table before planning any checks, so later categories
  have something to reason over besides a flat column list.</goal>
  <method>
  - Role-classify every column from name + dtype + cardinality: Identifier/Key-like,
    Categorical (low cardinality, repeated values), Measure (numeric, continuous),
    Temporal, Free-Text, Boolean/Flag.
  - Detect COMPANION GROUPS: columns whose names share a stem and differ only by a
    qualifier (numeric suffix like "1"/"2", role words like "Primary"/"Secondary",
    "Old"/"New", "Requested"/"Approved"). Treat each group as one semantic unit, not N
    independent columns.
  - Detect ENTITY-DEPENDENT columns: an Identifier/Key-like column (e.g. anything ending
    "ID", "Ref", "Code") implies the existence of a referenced entity. Any other column
    whose name shares the same qualifier word as that ID (e.g. an ID column qualified
    "Secondary" and a Status/Date/Amount column also qualified "Secondary") is a
    candidate DEPENDENT column - its population should logically track the ID's
    population.
  - Detect MAGNITUDE-RELATED measure pairs: two or more numeric columns whose names
    imply a known accounting/quantity relationship regardless of domain - one measures
    a whole and another a part of it (totals vs. components), or one is an input and the
    other a downstream derived value (e.g. anything read as "paid/covered/settled" vs.
    "billed/charged/revenue/premium"; "count" vs. "total"; "requested" vs. "approved").
    Name-pattern matching plus dtype is sufficient; no domain knowledge is required to
    flag the pair as worth a ratio check, only to interpret the result.
  </method>
  <output>A structured map: {column -> role}, {companion_group -> [columns]},
  {id_column -> [dependent columns]}, {measure_pair -> [column_a, column_b]}. Every
  category below reads from this map instead of re-deriving it.</output>
</discovery_protocol>

<category name="Uniqueness & Identity">
  <definition>The declared or inferred grain of the table is violated: duplicate keys,
  duplicate full rows, or a key that fails to uniquely identify a record.</definition>
  <generic_signal>Any column classified Identifier/Key-like by the discovery protocol,
  plus any minimal column combination whose cardinality equals row count.</generic_signal>
  <heuristic>Plan a strict uniqueness check on the primary key. Separately plan an
  exact-duplicate-row check across all non-key columns, since a duplicate key and a
  duplicate row are different failure modes with different causes.</heuristic>
  <check_template>{table}_primary_key_uniqueness; {table}_exact_duplicate_rows</check_template>
  <guardrail>A composite natural key with legitimately repeating components (e.g. one
  patient across many claims) is not a violation - only flag if the column(s) were
  identified as the grain-defining key.</guardrail>
</category>

<category name="Structural Completeness">
  <definition>A column is missing values it is structurally expected to have, based on
  its own declared role, independent of any other column.</definition>
  <generic_signal>Compute null-rate for EVERY column, not just ones a human named. Two
  sub-signals matter independently: (a) partial nullness on a column whose role implies
  it should usually be populated (an Identifier, a required Measure), and (b) 100%
  nullness on any column at all.</generic_signal>
  <heuristic>Plan a completeness sweep across all columns, not a hand-picked subset. A
  column that is null in 100% of rows is always worth flagging regardless of its
  declared purpose - a column that carries zero information is a defect class of its
  own (see Structural Degeneracy) even before considering *why* it's empty.</heuristic>
  <check_template>{table}_{column}_completeness_sweep (generated for every column)</check_template>
  <guardrail>Do not assume partial nullness is a defect on its own - cross-reference
  against Intra-Record Contradictions below before concluding a null is "wrong" rather
  than "legitimate business state."</guardrail>
</category>

<category name="Hidden and Polymorphic Nulls">
  <definition>Missingness disguised as a real value: whitespace, sentinel strings
  ("N/A", "NONE", "-", "UNKNOWN"), sentinel numbers (-1, 0 used as absence), or sentinel
  dates (far-past/far-future placeholders like 1900-01-01 or 9999-12-31).</definition>
  <generic_signal>For Categorical/Free-Text columns: any value that is empty after
  trimming whitespace, or any value that recurs suspiciously often relative to the
  column's other cardinality and resembles a placeholder token. For Temporal columns:
  any date sitting far outside the observed distribution in a suspiciously round way
  (year boundaries, epoch values). For Measures: a fixed sentinel value (often 0, -1, or
  999-repeated) that recurs far more often than a continuous distribution would predict.</generic_signal>
  <heuristic>Don't wait for a human to name the sentinel - profile each column's value
  distribution and flag any single value whose frequency is a statistical outlier
  relative to the rest of that column's distribution, when the column's role is not
  Boolean/Categorical-by-design.</heuristic>
  <check_template>{table}_{column}_polymorphic_null_scan</check_template>
  <guardrail>A uniform, dataset-wide constant is a different pattern than a polymorphic
  null and belongs in Structural Degeneracy instead - polymorphic nulls are
  characterized by masquerading as *one value among several legitimate ones*, not by
  being the only value present.</guardrail>
</category>

<category name="Validity and Domain Conformance">
  <definition>A value falls outside the set of values the column's role or observed
  distribution implies are legitimate.</definition>
  <generic_signal>For any Categorical column, the EMPIRICAL domain (the distinct values
  actually observed) is itself a signal even with no external spec: a small number of
  rows holding a value that no other row shares, especially a value that looks
  structurally different from the dominant set (different casing, different code
  scheme, an out-of-range code like 0 among 1/2), is a candidate violation.</generic_signal>
  <heuristic>Build the check from the data's own empirical majority pattern, not from a
  document. Flag minority values as candidates; treat majority-uniform values (present
  in 100% of rows, following one consistent format) as a design convention rather than a
  defect - uniform oddities are far more often intentional generation/system conventions
  than uniform defects, because a defect that hit every row would usually break
  something downstream and get caught earlier. A defect signature looks like a *minority*
  of rows disagreeing with the rest, not the whole column being unusual in the same way.</heuristic>
  <check_template>{table}_{column}_domain_conformance</check_template>
  <guardrail>If external documentation for the column is available, use it to confirm -
  not to originate - the check. The check must still be derivable from the data alone,
  since external docs won't exist for most tables the agent will ever see.</guardrail>
</category>

<category name="Format and Syntax Conformance">
  <definition>A column that looks structured (fixed-width codes, ZIP/postal codes,
  phone-shaped strings, ID-shaped strings) contains values that break the pattern the
  rest of the column follows.</definition>
  <generic_signal>Infer the expected pattern from the majority format actually observed
  in the column (e.g. length, character class, punctuation placement) rather than from a
  known format library - this keeps the check portable across countries/domains.</generic_signal>
  <heuristic>Plan a check for any column with high format regularity (i.e., most values
  match one shape) where a minority breaks that shape. Round/placeholder-looking breaks
  (all-zero, all-nine) are especially high-signal.</heuristic>
  <check_template>{table}_{column}_format_conformance</check_template>
  <guardrail>Free-text columns with genuinely variable content are exempt - this
  category only applies where the majority of values already share one shape.</guardrail>
</category>

<category name="Intra-Record Contradictions">
  <definition>Two or more columns within the same row imply mutually inconsistent facts.
  This is the most valuable and most commonly under-covered category because it can
  never be found by looking at one column at a time.</definition>
  <generic_signal>This category is driven entirely by the discovery protocol's
  COMPANION GROUPS and ENTITY-DEPENDENT column maps - it should never require a human to
  point at a specific pair.</generic_signal>
  <heuristic>
  For every companion group or ID→dependent-column mapping found in discovery, plan a
  fill-correlation check with one of these expected shapes (choose based on what the
  columns' roles imply, then verify against the data):
    (a) co-presence: both populated or both null together (e.g. a foreign entity's ID
        and that entity's descriptive fields should rise and fall together);
    (b) mutual exclusivity: at most one of the group is populated per row;
    (c) directional dependency: column B can only be populated if column A is (but not
        vice versa).
  Whichever shape the majority of rows follow, flag rows that break it. Do not assume
  the "obvious" direction - verify by counting both directions in the actual data before
  deciding which one is the violation, since the inverse of the expected pattern (as
  with a "Secondary" status field populated only when there is no secondary entity) is
  itself evidence of a defect, typically an upstream field-mapping bug.
  </heuristic>
  <check_template>{table}_{group_name}_fill_correlation; {table}_{id_column}_{dependent_column}_dependency</check_template>
  <guardrail>Distinguish a genuine contradiction from a legitimate business state by
  checking whether the "unexpected" pattern is consistent and total (every row with
  condition X behaves the same way) rather than scattered - a consistent inverse
  pattern across thousands of rows is a defect signature; a handful of scattered
  exceptions may be genuine edge cases.</guardrail>
</category>

<category name="Temporal Consistency">
  <definition>Multiple date/time columns in a row imply an order that is violated, or a
  date falls outside a plausible window (future dates, pre-founding dates).</definition>
  <generic_signal>Any two or more Temporal columns in the same companion group or
  otherwise co-referenced by name (created/updated, start/end, requested/approved,
  service/billed) imply a chronological sequence.</generic_signal>
  <heuristic>Plan a pairwise ordering check for every temporal pair discovery surfaces,
  plus a bounds check (no dates in the future relative to a load/reference date, no
  dates before a plausible system/business start).</heuristic>
  <check_template>{table}_{col_a}_{col_b}_chronology; {table}_{column}_future_date_check</check_template>
  <guardrail>Confirm which column is expected to come first from the name semantics
  before flagging - "updated" after "created" is expected; the reverse is the defect.</guardrail>
</category>

<category name="Statistical Plausibility and Magnitude Relationships">
  <definition>A numeric value, or the relationship between two numeric columns, falls
  outside what's statistically or logically plausible.</definition>
  <generic_signal>Two signals, both derivable without domain knowledge: (a) single-column
  outliers - values beyond N standard deviations or outside a plausible absolute range
  (negative ages, negative counts); (b) MEASURE PAIRS surfaced by discovery - compute the
  ratio of the two columns per row or in aggregate and check whether it clusters tightly
  or is wildly dispersed. A part/whole or input/output pair with a 2x-100x+ spread across
  otherwise-comparable rows is a signal worth surfacing even without knowing what the
  columns "really" mean.</generic_signal>
  <heuristic>Plan single-column outlier checks broadly. For measure pairs, plan a ratio-
  distribution check and flag it as a hypothesis (see guardrail) rather than an asserted
  defect, since the correct interpretation may depend on business context the agent
  doesn't have.</heuristic>
  <check_template>{table}_{column}_outlier_bounds; {table}_{measure_a}_{measure_b}_ratio_plausibility</check_template>
  <guardrail>Ratio/magnitude findings should always be surfaced as a hypothesis for
  human confirmation, per this KB's general semantic-anomaly guidance - the agent can
  detect "this ratio is implausible" reliably; it cannot always determine "and here is
  definitively why," since that depends on what the columns are meant to capture in this
  specific pipeline.</guardrail>
</category>

<category name="Structural Degeneracy">
  <definition>A column carries little or no information: fully empty, constant across
  every row, or dominated by one value with a near-empty long tail.</definition>
  <generic_signal>Compute distinct-value count and top-value frequency for every column
  as part of the same sweep as Structural Completeness - this is cheap and should never
  require a human to flag a specific column as "worth checking."</generic_signal>
  <heuristic>Flag any column that is 100% one value (zero variance) or where the
  frequency distribution has a category so rare (near-singleton) that any downstream
  segmentation by it would be statistically unreliable. These are lower severity than
  contradictions but should always be surfaced, since they silently break
  aggregations/joins/models downstream.</heuristic>
  <check_template>{table}_{column}_zero_variance; {table}_{column}_rare_category_flag</check_template>
  <guardrail>Not every constant column is a defect (e.g. a single-region extract will
  legitimately have one state value) - report as informational/low severity rather than
  a hard violation, and let the human decide if it matters for their downstream use.</guardrail>
</category>

<category name="Root-Cause Clustering">
  <definition>A meta-check, not a column-level check: multiple independently-planned
  findings turn out to be one underlying defect expressed across several columns.</definition>
  <generic_signal>After all other categories have produced their candidate checks,
  compare the ROW-SETS each check would flag (not just the column names). High overlap
  (the same rows keep recurring across otherwise-unrelated checks) is the signal.</generic_signal>
  <heuristic>When two or more planned checks' violating row-sets are near-identical or
  one is a strict subset of another, do not report them as N separate findings. Merge
  them into a single finding with a shared-root-cause hypothesis (e.g. "one upstream
  process populated four columns inconsistently for the same 1,929 rows" is one defect,
  not four). This is what separates a report a human can act on from a report that just
  lists symptoms.</heuristic>
  <check_template>{table}_root_cause_cluster (references the constituent check_names it merges)</check_template>
  <guardrail>Only merge when the overlap is structural (same exact rows, or one set
  strictly containing another) - coincidental partial overlap between unrelated checks
  should stay separate.</guardrail>
</category>

</knowledge_base>
"""