"""
Central configuration for the DQ agent system.

Keep this file boring: constants and simple lookups only. Nothing here
should contain business logic.
"""

from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()

# --- Paths ------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "synthea_dataset"
OUTPUT_DIR = BASE_DIR / "output"
KNOWLEDGE_BASE_PATH = BASE_DIR / "knowledge_base" / "dq_checks.md"
REPORT_PATH = OUTPUT_DIR / "dq_report.csv"

# --- Model --------------------------------------------------------------

# One model for every agent. If you later want a cheaper/faster model for
# a specific agent, override it in that agent's file only - don't add a
# config switch for something that isn't needed yet.
MODEL_NAME = "claude-sonnet-5"


def get_llm(temperature: float = 0) -> ChatAnthropic:
    """Return a fresh ChatAnthropic client. Every LLM agent builds its
    model this same way, so there's exactly one place to change it."""
    return ChatAnthropic(model=MODEL_NAME, temperature=temperature)


# --- Workflow rules ------------------------------------------------------

# Maximum number of times SQL Generator may be asked to fix failing SQL
# for a single table before the orchestrator gives up on that table.
MAX_RETRIES = 2

# The only worker agents the orchestrator is allowed to choose between.
# Keeping this list here (instead of duplicating it in the prompt and in
# graph.py) means there's one source of truth for "what the orchestrator
# can invoke".
WORKER_AGENTS = [
    "database_intelligence",
    "rule_creator",
    "sql_generator",
    "sql_validator",
    "sql_executor",
    "report_writer",
]

# SQL keywords the validator rejects. DQ checks are read-only by design -
# none of these should ever appear in generated SQL.
FORBIDDEN_SQL_KEYWORDS = [
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER",
    "CREATE", "TRUNCATE", "MERGE", "CALL", "REPLACE",
]