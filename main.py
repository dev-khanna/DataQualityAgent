"""
Entry point.

This is Layer 1: it creates state, builds the graph, and invokes the orchestrator, once per table.
"""

from config import DATA_DIR, OUTPUT_DIR, REPORT_PATH
from orchestrator import build_agent_graph
from state import initial_state_for_table
from tools.report_tools import read_report_from_disk
from utils.database import load_tables


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    tables = load_tables(DATA_DIR)
    if not tables:
        raise SystemExit(f"No CSV files found in {DATA_DIR}")

    print(f"Found {len(tables)} table(s): {tables}")

    app = build_agent_graph()

    dq_report: list[dict] = []
    for table_name in tables:
        print(f"\n=== {table_name} ===")
        state = initial_state_for_table(table_name, dq_report_so_far=dq_report)
        try:
            app.invoke(state, config={"recursion_limit": 100})
        except Exception as e:
            print(f"!! Table '{table_name}' failed and was skipped: {e}")
        dq_report = read_report_from_disk()

    print(f"\nDone. {len(dq_report)} issue(s) recorded.")
    print(f"Report saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()