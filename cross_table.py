"""
Cross-Table DQ Issues Detector.

This is the counterpart to orchestrator.py's single-table branch. Once
all tables' metadata has been collected (see tools/database_tools.py),
the run splits into two independent sections - this is the cross-table
half, which will eventually reason about relationships BETWEEN tables
(referential integrity, FK consistency, master-data reconciliation).

Intentionally a no-op for now ("leave blank for now"). state.py already
reserves `related_table` on PlannedCheck/CompiledRule and knowledge_base
already documents that cross-table checks are out of scope for
single-table reasoning - so wiring this branch in later is a logic
change here, not a state or schema migration.
"""

from state import TableMetadata


def run_cross_table_detection(tables: list[str], metadata_by_table: dict[str, TableMetadata]) -> None:
    """Entry point for the cross-table DQ branch. Currently does
    nothing - reserved for future referential-integrity / cross-table
    checks that plan and run against `related_table` the same way the
    single-table branch does against `table`."""
    return None