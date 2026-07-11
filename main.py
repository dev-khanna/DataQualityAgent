"""
Entry point.

Loads every table in data/synthea_dataset as a DuckDB table, runs the
supervisor graph until every table has been processed, and writes the
final DQ report.
"""

from config import DATA_DIR, OUTPUT_DIR, REPORT_PATH
from graph import build_graph
from state import initial_state
from utils.database import load_tables


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    tables = load_tables(DATA_DIR)
    if not tables:
        raise SystemExit(f"No CSV files found in {DATA_DIR}")

    print(f"Found {len(tables)} table(s): {tables}")

    app = build_graph()
    state = initial_state(tables)

    final_state = app.invoke(state, config={"recursion_limit": 500})

    print(f"Done. {len(final_state['dq_report'])} issue(s) recorded.")
    print(f"Report saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()