"""
Entry point.

Metadata for every table is collected deterministically, up front,
before the agent ever runs - the orchestrator starts already knowing
every table, rather than fetching metadata table-by-table.
"""

from config import DATA_DIR, OUTPUT_DIR, REPORT_PATH
from orchestrator import build_agent_graph
from state import initial_state_for_run
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

    app = build_agent_graph()
    state = initial_state_for_run(usable_tables, metadata_by_table)

    try:
        app.invoke(state, config={"recursion_limit": 300})
    except Exception as e:
        print(f"!! Run failed: {e}")

    dq_report = read_report_from_disk()
    print(f"\nDone. {len(dq_report)} issue(s) recorded.")
    print(f"Report saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()