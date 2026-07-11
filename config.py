"""
Central configuration for the DQ agent system.

Keep this file boring: constants and simple lookups only. Nothing here should contain business logic.
"""

from pathlib import Path
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "synthea_dataset"
OUTPUT_DIR = BASE_DIR / "output"
KNOWLEDGE_BASE_PATH = BASE_DIR / "knowledge_base" / "dq_checks.md"
REPORT_PATH = OUTPUT_DIR / "dq_report.csv"

#defining models
open_router_model = init_chat_model(
    "nvidia/nemotron-3-super-120b-a12b:free",
    model_provider="openrouter",
    temperature=0,
    max_tokens=2000,
)
gemini_model = init_chat_model(
    "gemini-3.1-flash-lite", 
    model_provider="google_genai",
    temperature=0,
    max_tokens=2000,
)


def get_llm()->BaseChatModel:
    return gemini_model


# Maximum number of times SQL Generator may be asked to fix failing SQL for a single table before the orchestrator gives up on that table.
MAX_RETRIES = 2

# SQL keywords the validator rejects. DQ checks are read-only by design & therefore none of these should ever appear in generated SQL.
FORBIDDEN_SQL_KEYWORDS = [
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER",
    "CREATE", "TRUNCATE", "MERGE", "CALL", "REPLACE",
]