"""
Entry point.

Metadata for every table is collected deterministically, up front,
before either detection branch ever runs - nothing fetches metadata
table-by-table.

Once metadata is collected, the run splits into two independent
sections (see the V2 architecture diagram): cross-table detection
(cross_table.py - currently a no-op placeholder, called once with every
table's metadata since cross-table reasoning inherently needs more than
one table at a time) and single-table detection (orchestrator.py).

Single-table detection runs ONE agent invocation PER TABLE, in a loop
right here - not one invocation covering every table. Each table's
run is independent; report_tools.read_report_from_disk/write_report is
what stitches their results into one continuous report on disk.
"""

from config import DATA_DIR, OUTPUT_DIR, REPORT_PATH
from cross_table import run_cross_table_detection
from orchestrator import run_single_table_detection
from tools.database_tools import extract_all_metadata
from tools.report_tools import read_report_from_disk
from utils.database import load_tables


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    tables = load_tables(DATA_DIR)
    if not tables:
        raise SystemExit(f"No CSV files found in {DATA_DIR}")

    print(f"Found {len(tables)} table(s): {tables}")
    print("Collecting metadata for all tables...")
    metadata_by_table = extract_all_metadata(tables)

    usable_tables = list(metadata_by_table.keys())
    if not usable_tables:
        raise SystemExit("Metadata extraction failed for every table - nothing to run.")
    skipped = set(tables) - set(usable_tables)
    if skipped:
        print(f"Skipping table(s) with failed metadata extraction: {sorted(skipped)}")

    print("Metadata extraction complete. Splitting into cross-table and single-table detection...")
    run_cross_table_detection(usable_tables, metadata_by_table)

    for table in usable_tables:
        print(f"\n--- Single-table DQ checks: '{table}' ---")
        run_single_table_detection(table, metadata_by_table[table])
        print(f"    report now has {len(read_report_from_disk())} row(s) after '{table}'.")

    dq_report = read_report_from_disk()
    print(f"\nDone. {len(dq_report)} issue(s) recorded.")
    print(f"Report saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()