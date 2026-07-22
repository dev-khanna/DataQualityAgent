"""
config.py

All the constants in our pipeline are established here.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" 

GEMINI_MODEL_NAME = "gemini-3.1-flash-lite"
GEMINI_MODEL_PROVIDER = "google_genai"
GEMINI_TEMPERATURE = 1
GEMINI_MAX_TOKENS = 32000
GEMINI_THINKING_LEVEL = "high"

OPENROUTER_MODEL_NAME = "nvidia/nemotron-3-super-120b-a12b:free"
OPENROUTER_MODEL_PROVIDER = "openrouter"
OPENROUTER_TEMPERATURE = 0
OPENROUTER_MAX_TOKENS = 5000

REPORT_PATH = BASE_DIR / "dq_report.csv"

TODO_DIR = BASE_DIR / "todo_list.md"

SAMPLE_ROWS_LIMIT = 20

NEAR_CANDIDATE_KEY_THRESHOLD = 0.75

# A column with at most this many distinct values is treated as a closed
# set of categories, and gets its raw value counts profiled (see
# get_low_cardinality_value_counts) so the rule planner can spot typos
# and normalization issues (RULE_PLAN_SYSTEM_PROMPT clue 4).
LOW_CARDINALITY_MAX_DISTINCT = 30

# How many times execute_sql will let the orchestrator fix and resubmit a
# rule's queries before the rule is dropped automatically (see
# INDIVIDUAL_TABLE_DQ_SYSTEM_PROMPT's <workflow> step 3).
MAX_RETRIES = 3

MAX_VIOLATION_ROWS_SHOWN = 20

FORBIDDEN_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE",
    "ATTACH", "DETACH", "COPY", "EXPORT", "IMPORT", "PRAGMA", "CALL",
    "GRANT", "REVOKE", "TRUNCATE", "VACUUM", "INSTALL", "LOAD",
}
