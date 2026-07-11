# Single-Table Data Quality Knowledge Base

## Purpose and Scope

This document is a permanent reference for reasoning about data quality within a single, isolated table. It is intended to be supplied as background knowledge to an autonomous planning agent whose job is to decide *what to check* and *why* when it encounters a table, based only on the table name, column names, data types, primary/candidate keys, and sample values.

This knowledge base deliberately excludes anything that requires information outside the table itself: joins, foreign key relationships, referential integrity, master data reconciliation, lineage tracing, cross-table consistency, and business rules that cannot be inferred from the table's own structure and contents. Everything here is inferable from one table in isolation.

For every issue type, this document describes what it is, why it happens, how an experienced data engineer recognizes it, its detection category, and its typical importance. No implementation instructions, query language, or software-specific behavior is included — this is conceptual, reusable domain knowledge.

---

## Part I — Foundational Framework

### 1.1 The Three Detection Categories

Every data quality issue in this knowledge base is classified into one of three categories. This classification determines the *nature of reasoning* an agent must apply, not just the technique used.

- **Deterministic** — The issue can be identified with a binary, unambiguous rule applied to a single value or row. There is no judgment call: a value either satisfies the rule or it does not (e.g., a field is empty, a value fails a pattern, a date is not a valid calendar date). Deterministic checks require only the definition of a rule; they do not require inspecting the broader dataset.
- **Statistical** — The issue can only be identified by examining the distribution, frequency, or shape of values across many rows. A single value in isolation is not obviously wrong; it is the aggregate pattern that reveals the anomaly (e.g., a value is 40 standard deviations from the mean, or a category that never previously exceeded 5% of rows suddenly represents 95%). Statistical checks require a population, a baseline, or a distribution to compare against.
- **Semantic** — The issue requires real-world, domain-level understanding of what a column *means* to determine whether a value is sensible, even though the value is perfectly valid in type and format. Semantic issues sit at the boundary of what can be inferred from structure alone; strong semantic reasoning is possible from naming conventions and value co-occurrence even without external business documentation.

Many real-world issues span more than one category (for example, unit-of-measure mixing is fundamentally a semantic problem — "this column means kilograms" — but is *detected* through statistical means, such as a bimodal distribution). Where this overlap exists, it is called out explicitly.

### 1.2 The Importance Framework

Each issue is rated for typical relative importance. This rating reflects how severely the issue tends to distort downstream analytics, decision-making, or system behavior if left uncorrected, not how common it is.

- **HIGH** — Issues that structurally break downstream processing, silently corrupt calculations, cause duplicate counting, or make a dataset actively misleading rather than merely imperfect.
- **MEDIUM** — Issues that degrade quality, trustworthiness, or usability, and will eventually cause problems, but do not immediately invalidate results or break processing.
- **LOW** — Cosmetic or minor issues that are worth flagging but rarely change conclusions or break systems on their own.

Importance is contextual — a LOW-rated issue in a general-purpose table may become HIGH if the column in question is a primary key, a financial amount, or a join/lookup candidate. An agent should treat these ratings as priors, not absolutes, and adjust based on the specific role a column appears to play (identifier, monetary amount, timestamp, category flag, free-text description, etc.).

### 1.3 How an Agent Should Read a Table Before Checking It

Before selecting checks, an experienced engineer forms a mental model of the table:

1. **Grain** — What does one row represent? (a transaction, a person, a daily snapshot, an event). This is inferred from the table name, the primary/candidate key, and whether timestamps or sequence-like columns are present.
2. **Roles of columns** — Which columns are identifiers, which are measures, which are categorical/dimensional, which are free text, which are temporal. Naming patterns (`_id`, `_at`, `_date`, `is_`, `has_`, `_flag`, `_code`, `_status`, `_amount`, `_pct`) are strong signals even without documentation.
3. **Expected cardinality** — Whether a column should be unique per row (an identifier), low-cardinality (a status/category), or high-cardinality/continuous (an amount or free text).
4. **Expected relationships between columns within the row** — Whether any columns are logically dependent on each other (a start and end date, a status and a corresponding detail field, a quantity and a total).

This mental model is what allows an agent to select the *right subset* of checks below rather than running everything indiscriminately against every column.

---

## Part II — Completeness

Completeness evaluates whether the information required to make a row useful is actually present — not merely whether a system-level `NULL` is absent, but whether meaningful, usable content exists.

### 2.1 Hidden and Polymorphic Nulls
**What it is:** Missing values disguised as non-null content — empty strings, whitespace-only strings, or sentinel placeholder text such as "N/A", "unknown", "TBD", "none", "-", or "999".
**Why it occurs:** Source applications lack mandatory field enforcement, or integration pipelines insert placeholder text specifically to satisfy a non-null constraint without a genuine value being available.
**Recognition:** An experienced engineer treats any true null-rate calculation as incomplete until it also accounts for a frequency scan of the most common values in a column — a suspiciously high frequency of short, generic, or repeated strings is a signal that "null" is being encoded as text rather than as an actual null. Whitespace-only strings are a specific and common trap because they pass naive "is not null" and "is not empty string" checks simultaneously.
**Category:** Deterministic.
**Importance:** HIGH — hidden nulls silently deflate true completeness metrics and corrupt any aggregation or grouping performed on the column.

### 2.2 Partial Record Population
**What it is:** A row exists and passes basic insertion, but lacks enough populated fields to be operationally meaningful — for example, a customer record with only a first name and no other identifying or contact information.
**Why it occurs:** Multi-step data entry or onboarding flows that users abandon partway through; asynchronous form submissions that capture partial state before a session ends; upstream systems that create a placeholder row before the rest of the data arrives (and the rest never does).
**Recognition:** Engineers assess the density of populated fields per row rather than evaluating each column independently — a row can pass every individual completeness check and still be functionally useless if only one or two of many expected fields are filled. Distinguishing "acceptable optional fields" from "fields that jointly define usefulness" requires understanding which fields are core to the row's grain.
**Category:** Deterministic.
**Importance:** MEDIUM to HIGH, depending on whether the populated fields are sufficient to support the table's primary use case.

### 2.3 Missing Entire Partitions
**What it is:** A contiguous, expected slice of data — most often a date range, but potentially any expected segment such as a source system or batch — is entirely absent from the table, rather than merely having incomplete rows within it.
**Why it occurs:** A scheduled load failed silently, an upstream system had an outage, an extraction job timed out before writing any rows for that segment, or a partition was accidentally dropped or overwritten.
**Recognition:** This is invisible at the row level — every row that exists may be perfectly valid — and can only be found by comparing the *set of partitions actually present* against the *set of partitions that should exist* given the table's known cadence (e.g., daily, hourly). A gap in a time series of row counts by day/week/month is the classic signature.
**Category:** Deterministic (once the expected cadence is known, the check itself is a simple presence/absence test), though establishing the expected cadence often requires observing the table's own history.
**Importance:** HIGH — missing partitions cause systematic undercounting and are among the most damaging completeness failures because they are easy to miss when only spot-checking individual rows.

---

## Part III — Validity and Format Conformance

Validity evaluates whether data that *is* present structurally and syntactically conforms to the rules implied by its column name, declared type, and observed patterns elsewhere in the same column.

### 3.1 Syntactic and Format Violations
**What it is:** Values that exist but break an expected structural pattern — an email address without an "@" symbol, phone numbers containing letters, inconsistent date formatting within the same column, or postal codes with the wrong number of characters.
**Why it occurs:** Source applications accept free-text input without validating structure at the point of entry, or data merged from multiple upstream systems each formatted values differently before consolidation.
**Recognition:** The most reliable technique is to profile the observed patterns actually present in a column and compare their frequency distribution — if 95% of values in a column named `phone_number` follow one shape and 5% follow a visibly different shape, the minority is very likely a format violation rather than a legitimate variant. Column *naming* strongly narrows down which pattern family to expect (an `_email` suffix implies one structural family, a `_zip`/`_postal_code` suffix implies another).
**Category:** Deterministic.
**Importance:** MEDIUM to HIGH — depends on whether the column is used downstream for matching, contact, or system integration (in which case format errors are functionally blocking) versus purely descriptive display (in which case they are cosmetic).

### 3.2 Domain and Allowed-Value Violations
**What it is:** A field contains a value outside its defined set of permissible categories — an unrecognized country code, or a status value that doesn't match any of the table's other observed status values.
**Why it occurs:** Incomplete mapping during system migrations or integrations; reference/lookup value sets that were updated at the source but never propagated; free-text entry into what should be a constrained field; legacy values that predate a later restriction of the allowed set.
**Recognition:** For any column that behaves categorically (low distinct-value count relative to row count, especially with naming like `_status`, `_type`, `_category`, `_code`), an engineer enumerates the full distinct value set and inspects it for outliers — values that appear only once or a handful of times, unexpected casing variants of an otherwise-valid value (e.g., "active" vs. "Active" vs. "ACTIVE"), or values that look like a typo of a legitimate category.
**Category:** Deterministic once the allowed set is known; establishing the allowed set from the table alone is closer to semantic/statistical inference (inferring the set from what is common and treating rare distinct values as suspect).
**Importance:** HIGH for columns that drive branching logic or reporting segmentation; MEDIUM otherwise.

### 3.3 Data Type Mismatches
**What it is:** A column stores values in an inappropriate underlying type for its meaning — numeric identifiers stored as text, dates stored as free-text strings, or boolean concepts inconsistently represented as `1`/`0` in some rows and `Y`/`N`/`true`/`false` in others.
**Why it occurs:** File-based exchange formats (spreadsheets, delimited text) have no native strong typing, so numeric-looking values lose leading zeros, gain thousands-separators, or get auto-converted by intermediate tools; schema-on-read systems store everything as text by default until explicitly cast.
**Recognition:** A column whose declared or apparent type is generic text but whose values are overwhelmingly numeric- or date-shaped is a signal worth investigating, especially when a subset of values contain stray formatting characters (commas, currency symbols, extra whitespace) that would prevent a clean type cast. Mixed boolean representations are recognized by enumerating distinct values in a column expected to be binary and finding more than two semantically-equivalent forms.
**Category:** Deterministic.
**Importance:** HIGH — type mismatches break arithmetic, sorting, and comparison operations and often fail silently rather than throwing visible errors.

### 3.4 Precision and Scale Truncation
**What it is:** Numeric or string data that has been unexpectedly shortened — financial values losing decimal precision, or long text fields cut off mid-word.
**Why it occurs:** A downstream system enforces a rigid field-length or column-width limit at ingestion and silently truncates anything longer; floating-point representation and casting between numeric types introduces rounding or precision loss.
**Recognition:** A conspicuous cluster of string values whose length is exactly at (or one below) a round number such as 50, 100, or 255 characters is a strong signal of length-based truncation, especially if a meaningful number of those values appear to end mid-word rather than at a natural sentence boundary. For numeric fields, monitoring the distribution of decimal places observed in a column that should represent currency or a precise measurement — and flagging a sudden narrowing of that distribution — reveals precision loss.
**Category:** Deterministic (for detecting the pattern), though the interpretation that it represents *truncation* rather than legitimate short values is closer to semantic judgment.
**Importance:** MEDIUM to HIGH depending on whether the affected column is financial or otherwise precision-sensitive.

### 3.5 Encoding and Character Set Corruption
**What it is:** Text fields containing garbled, unreadable symbol sequences — commonly called "mojibake" — where recognizable characters are replaced with nonsensical substitutions.
**Why it occurs:** A mismatch between the character encoding used to write the data and the encoding used to read it, most often when UTF-8 encoded text is misinterpreted under a single-byte encoding standard (or the reverse) somewhere in the data's transit path.
**Recognition:** Engineers scan text columns for recurring, non-random sequences of special or unusual symbols that appear anywhere accented characters, non-Latin scripts, or certain punctuation (curly quotes, em-dashes) would be expected — these corrupted sequences tend to repeat in a structured, recognizable way rather than being genuinely random, which distinguishes them from ordinary noisy free text.
**Category:** Deterministic.
**Importance:** MEDIUM — usually cosmetic and localized to display, but can be HIGH if the corrupted values are also used as matching or grouping keys, since visually similar corrupted variants will be treated as distinct values.

---

## Part IV — Uniqueness

Uniqueness ensures each distinct real-world entity or event is represented exactly once in the table, so that counts, sums, and aggregations are not inflated by unintended repetition.

### 4.1 Exact Intra-Table Duplicates
**What it is:** Two or more rows that are identical across every column, representing the same event or record repeated verbatim.
**Why it occurs:** Retry logic in an upstream pipeline resubmits a record after a failure without idempotency protection; a source application allows the same form submission to be sent twice; a batch job is re-run without first clearing its prior output.
**Recognition:** Engineers compare the count of distinct full rows to the count of total rows; any gap indicates exact duplication. This is most meaningful when there is no declared primary key, since a table with a properly enforced unique key cannot have exact duplicates by construction — the presence of exact duplicates is itself evidence that no such constraint is being enforced.
**Category:** Deterministic.
**Importance:** HIGH — directly inflates counts, sums, and any downstream aggregate.

### 4.2 Intra-Table Fuzzy and Near-Duplicates
**What it is:** Multiple rows that represent the same real-world entity but differ in spelling, formatting, capitalization, abbreviation, or minor detail — "John Smith" versus "Jon Smith", or "Acme Corp" versus "Acme Corporation".
**Why it occurs:** Records are created through multiple independent entry channels (manual entry, imports, web forms, integrations) with no deduplication or entity-matching applied at the point of ingestion, allowing the same entity to accumulate slightly different representations over time.
**Recognition:** This requires comparing values *across rows* for similarity rather than checking any single value in isolation — string-distance closeness, shared tokens, or matching normalized forms (lowercased, punctuation-stripped, whitespace-collapsed) between otherwise-distinct values in an identity-bearing column (names, company names, addresses) are the signal. High-cardinality free-text identity columns are the primary target for this check; low-cardinality categorical columns are not, since apparent "near-duplicates" there are more likely genuine distinct categories.
**Category:** Statistical (probabilistic matching across the population of values).
**Importance:** MEDIUM to HIGH — silently fragments what should be a single entity into several, distorting any per-entity aggregation.

### 4.3 Primary Key Uniqueness Violations
**What it is:** The column or column-combination intended to uniquely identify each row contains duplicate values.
**Why it occurs:** Bulk loads that bypass constraint enforcement for performance reasons; auto-increment or sequence-generation collisions, often after a system migration or restart; manual inserts that bypass the application layer where uniqueness is normally enforced.
**Recognition:** Engineers identify the declared or candidate primary key (often inferable from a column literally named `id`, `_id`, or a composite of columns whose combined values are expected to be unique per the table's grain) and check the frequency distribution of that key — any value with a count greater than one is a violation. When no explicit primary key is declared, an engineer infers candidate keys by testing which column or column-combination has a distinct-value count equal to the total row count.
**Category:** Deterministic.
**Importance:** HIGH — this is one of the most severe issues possible in a single table, since it breaks the fundamental assumption that one row equals one entity, and cascades into every other quality dimension.

---

## Part V — Intra-Record Consistency and Logic

Consistency evaluates whether the fields *within a single row* agree with each other and with basic physical and temporal reality, independent of any other row.

### 5.1 Intra-Record Contradictions
**What it is:** Two or more fields in the same row logically conflict — a marital status of "Single" alongside a fully populated spouse name field, or a status of "Cancelled" alongside a populated shipment tracking number.
**Why it occurs:** An application updates one field in response to a business event but fails to update a logically dependent field at the same time, leaving the record in an internally inconsistent state.
**Recognition:** This requires identifying pairs or groups of columns whose *names* imply a dependency relationship (a status field and a detail field that should only be populated for certain status values; a boolean flag and a field that should only exist when the flag is true) and checking whether that implied relationship actually holds across the data. Column naming conventions are the primary clue an agent has to infer these dependencies without external documentation.
**Category:** Semantic.
**Importance:** MEDIUM to HIGH depending on how central the contradicting fields are to the table's core purpose.

### 5.2 Invalid Temporal Logic
**What it is:** Dates or timestamps within a single row that contradict chronological reality — an end date before its corresponding start date, a shipped date before an order date, or a modified timestamp earlier than a created timestamp.
**Why it occurs:** Out-of-order event processing in distributed systems, clock synchronization drift between servers, network delays that cause a "later" event to be recorded with an earlier timestamp, or users manually overriding date fields in a source application without validation.
**Recognition:** Any table with two or more temporal columns should have the *implied* ordering between them checked — this ordering is usually obvious from naming (`start`/`end`, `created`/`updated`, `order`/`ship`/`deliver`) even without documentation. A violation is any row where the naturally-expected earlier date is chronologically later than the naturally-expected later date.
**Category:** Deterministic.
**Importance:** HIGH — temporal logic violations often indicate deeper pipeline timing problems and corrupt any duration or sequence-based calculation.

### 5.3 Semantic Validity Failures
**What it is:** A value that is syntactically and type-correct but represents a real-world impossibility — a negative age, an age of 300 years, or a pregnancy-related field populated for a record otherwise indicated as male.
**Why it occurs:** Source systems enforce structural validation (correct type, correct format) but do not enforce deeper real-world business logic, because that logic requires domain knowledge the input form or schema does not encode.
**Recognition:** This is the deepest form of single-table reasoning: an engineer applies general real-world knowledge about what a column's name implies is possible (ages cannot be negative or exceed roughly 120; a percentage column should not exceed 100 unless explicitly scaled; a quantity column should not be negative unless the table clearly represents adjustments or returns) and checks observed values against that boundary. This differs from a plain outlier check (3.1 in the accuracy section) because the value isn't merely statistically unusual — it is categorically impossible regardless of the surrounding distribution.
**Category:** Semantic.
**Importance:** HIGH — these values are unambiguous errors (not just unusual data points) and typically indicate an entry, mapping, or transformation defect.

---

## Part VI — Accuracy and Statistical Anomalies

These checks determine whether structurally valid data represents a realistic and stable state, using the distribution of the data itself as the basis for judgment.

### 6.1 Domain Outliers and Extreme Values
**What it is:** Values that are technically valid for their type but statistically or physically implausible given the rest of the column's distribution — a recorded temperature of 10,000°C, or a single transaction of $10,000,000 in a column where typical values are two or three orders of magnitude smaller.
**Why it occurs:** Manual entry mistakes (an extra digit, a misplaced decimal point), unit confusion at the point of entry, or upstream aggregation/transformation errors that inflate a value before it lands in the table.
**Recognition:** Engineers characterize the typical range of a numeric column (using measures such as spread around the mean or the interquartile range) and flag values that fall far outside that range. The judgment of "far outside" should account for the column's natural variability — a column that is naturally highly variable (e.g., transaction amounts across wildly different customer sizes) tolerates a wider range before a value is truly suspect than a column that is naturally tightly clustered (e.g., a percentage or a rating score).
**Category:** Statistical.
**Importance:** MEDIUM to HIGH — a small number of extreme outliers can dominate sums and averages even when they represent a tiny fraction of rows.

### 6.2 Unit of Measure Mismatches
**What it is:** A single column invisibly mixes more than one unit of measurement — weights recorded in both kilograms and pounds, or monetary values recorded in both raw units and thousands, within the same column.
**Why it occurs:** Data streams from multiple sources or regions are merged without unit normalization, or different operators/systems interpret an ambiguous input field differently.
**Recognition:** The telltale sign is a distribution with two or more distinct clusters (a bimodal or multimodal shape) in a column that should otherwise represent one continuous, unimodal measurement — for example, a weight column with one cluster around 150 and another around 70 is consistent with pounds and kilograms for human body weight coexisting in the same field. This is fundamentally a semantic problem (the column has two different *meanings* mixed together) but its footprint is statistical (an unnatural distribution shape), which is why it spans both categories.
**Category:** Statistical, with semantic origin.
**Importance:** HIGH — this error is invisible at the row level and produces systematically wrong aggregates and averages until identified.

### 6.3 Data Skew and Distribution Drift
**What it is:** The statistical properties of a column change unexpectedly over time or deviate from a previously stable pattern — a category that suddenly accounts for the overwhelming majority of rows, or the mean and variance of a numeric field shifting sharply.
**Why it occurs:** A pipeline transformation bug that silently maps many distinct values into a single fallback category, an upstream configuration change that alters how a field is populated, or a genuine and unannounced shift in the underlying business process being recorded.
**Recognition:** This requires a baseline — either a historical snapshot of the same table or an internally stable segment (e.g., an earlier date partition) to compare against — and measuring how far the current distribution has moved from that baseline. A category value newly dominating a column that was previously well-distributed, or a numeric column's central tendency moving by a large margin between periods, are the classic signatures.
**Category:** Statistical.
**Importance:** MEDIUM to HIGH — drift corrupts any model or report trained or calibrated on the historical pattern, even though every individual value remains structurally valid.

### 6.4 Record Count Anomalies
**What it is:** A sudden, large spike or drop in the total number of rows landing in the table relative to its historical baseline volume.
**Why it occurs:** A pipeline transformation error, a dropped ingestion event, a failed or partially-failed batch job, or an unintended join/expansion upstream that multiplies rows before they reach the table.
**Recognition:** Engineers track the row count (overall, or by natural partition such as day) over time and compare each new observation against the recent historical trend and its normal variability, flagging counts that fall well outside the expected range in either direction.
**Category:** Statistical.
**Importance:** HIGH — count anomalies are often the earliest and most reliable signal that something upstream has broken, frequently preceding and explaining other quality issues found elsewhere in the table.

---

## Part VII — Timeliness

Timeliness evaluates whether the data is current enough, relative to its own expected refresh cadence, to be trustworthy for the decisions it is meant to support.

### 7.1 Data Staleness and Ingestion Lag
**What it is:** Data that is factually correct about the past but has arrived, or been refreshed, much later than expected, making it too old to reliably represent the present state of whatever it describes.
**Why it occurs:** Network delays, a delayed batch schedule, timeouts in the ingestion process, or an upstream source that itself has become slow or intermittent.
**Recognition:** Engineers compare the most recent timestamp present in the table (a `created_at`, `updated_at`, or equivalent column) against the current time and against the table's known or inferred refresh cadence — a table that historically updates daily but has not received new rows in several days is stale even though every existing row remains individually valid.
**Category:** Deterministic.
**Importance:** MEDIUM to HIGH depending on how time-sensitive the table's use case is; near-real-time operational tables treat staleness as HIGH, while slowly-changing reference tables treat it as LOW.

---

## Part VIII — Semantics and Hidden Meaning

Semantic failures occur when a table's physical structure remains completely intact, but the true meaning, interpretation, or contextual accuracy of the values it contains has been corrupted.

### 8.1 Improper Default Substitution
**What it is:** `NULL` values that have been replaced with sentinel placeholder values that are technically valid data — dates such as "1900-01-01" or "9999-12-31", or numeric sentinels such as "-1" or "0" — rather than being left null or properly flagged as missing.
**Why it occurs:** A pipeline or application enforces a non-null constraint but has no genuine value to insert, so it substitutes an arbitrary placeholder to satisfy the constraint, treating the missing-value problem as solved when it has only been hidden.
**Recognition:** Engineers scan date and numeric fields for a disproportionately high frequency of exact, suspicious edge-case values — dates sitting exactly at the earliest or latest representable value, or an unnatural spike of exact zeroes in a field where a smooth, continuous distribution would otherwise be expected. The key signal is *disproportion*: a legitimate value of zero or a legitimate historical date is expected occasionally, but an outsized spike concentrated on one exact value is a strong indicator of substitution rather than genuine data.
**Category:** Semantic.
**Importance:** HIGH — these substituted values silently distort every downstream calculation involving age, duration, or numeric aggregation, and are especially dangerous because they pass all type and format validation.

### 8.2 Semantic Drift
**What it is:** The underlying business meaning of a column changes silently over time without any corresponding change to its data type, name, or physical schema — for example, a column tracking "active customer" status quietly being redefined from a 90-day purchase window to a 30-day login window.
**Why it occurs:** Definitions evolve as business processes change, but historical data is never reprocessed under the new definition, and the schema itself gives no indication that a redefinition has occurred.
**Recognition:** This is the hardest issue in this knowledge base to detect from a single table alone, since the schema is identical before and after the drift. The most reliable single-table signal is an unexplained shift in an aggregated metric derived from the column (an inflection point where a proportion, rate, or count meaningfully and permanently changes level) that cannot be attributed to volume, seasonality, or any other already-identified quality issue. Because true confirmation requires external business context, an agent operating on a single table should treat this as a *hypothesis to raise* rather than a *fact to assert*.
**Category:** Semantic.
**Importance:** MEDIUM — difficult to detect with certainty from structure alone, but potentially HIGH impact if confirmed, since it silently invalidates historical comparisons.

---

## Part IX — Column-Type Reasoning Guide

This section consolidates the dimensions above into practical guidance organized by the *kind* of column being examined, since this is typically how an agent will approach an unfamiliar table — column by column.

### 9.1 Identifier Columns (`_id`, `_key`, `_code` used as row identity)
Primary relevant issues: Primary Key Uniqueness Violations (5.3... see 4.3), Exact Duplicates (4.1), Data Type Mismatches (3.3 — identifiers stored inconsistently as text versus numeric), Hidden Nulls (2.1 — a missing identifier is especially severe). An agent should first determine whether a column is functioning as the row's identity before applying any of these checks with high priority.

### 9.2 Categorical / Enumerated Columns (`_status`, `_type`, `_category`, `_flag`)
Primary relevant issues: Domain and Allowed-Value Violations (3.2), Data Skew and Distribution Drift (6.3), Intra-Record Contradictions (5.1) when paired with dependent detail fields. An agent should always enumerate the full distinct value set for these columns early, since it cheaply reveals several issue types at once.

### 9.3 Numeric / Measure Columns (`_amount`, `_price`, `_qty`, `_pct`, `_score`)
Primary relevant issues: Domain Outliers (6.1), Unit of Measure Mismatches (6.2), Precision and Scale Truncation (3.4), Semantic Validity Failures (5.3 — impossible values such as negative counts), Improper Default Substitution (8.1 — sentinel zeroes or negative-one values).

### 9.4 Temporal Columns (`_date`, `_at`, `_time`, `_timestamp`)
Primary relevant issues: Invalid Temporal Logic (5.2), Syntactic and Format Violations (3.1 — mixed date formats), Improper Default Substitution (8.1 — sentinel min/max dates), Data Staleness (7.1), Missing Entire Partitions (2.3) when the column defines the table's natural time series.

### 9.5 Free-Text Columns (names, descriptions, addresses, notes)
Primary relevant issues: Fuzzy and Near-Duplicates (4.2), Encoding Corruption (3.5), Precision/Length Truncation (3.4), Hidden Nulls disguised as placeholder text (2.1).

### 9.6 Boolean / Binary Columns (`is_`, `has_`)
Primary relevant issues: Data Type Mismatches (3.3 — inconsistent true/false representations), Intra-Record Contradictions (5.1) when paired with a dependent field that should only be populated for one of the two states.

---

## Part X — Prioritization Heuristics for an Autonomous Agent

When planning which checks to run against an unfamiliar table under limited time or compute, the following heuristics reflect how experienced engineers triage:

1. **Start with identity.** Establish the table's grain and its primary/candidate key before anything else — Uniqueness violations on the key (4.3) invalidate the reliability of every other check performed afterward, since they mean "one row" does not actually mean "one entity."
2. **Check volume and partition coverage next.** Record Count Anomalies (6.4) and Missing Partitions (2.3) are cheap to check and, if present, often explain or amplify many issues found later — it is more efficient to discover a missing day of data before spending effort profiling individual columns within that day.
3. **Profile distinct values before writing rules.** Enumerating the distinct value set of every low-cardinality column early reveals Domain Violations (3.2), Hidden Nulls (2.1), Data Type Mismatches (3.3), and gives the raw material needed for Semantic Drift hypotheses (8.2), all from a single, cheap operation.
4. **Reserve statistical and semantic checks for columns where they matter most.** Outlier detection (6.1), fuzzy matching (4.2), and unit-mismatch detection (6.2) are comparatively expensive and are best targeted at columns already identified as measures or identity-bearing free text, rather than run uniformly across every column.
5. **Treat semantic findings as hypotheses, not verdicts.** Because Part VIII issues cannot be fully confirmed from a single table alone, an agent should surface them with appropriate confidence framing rather than presenting them with the same certainty as a deterministic rule violation.
