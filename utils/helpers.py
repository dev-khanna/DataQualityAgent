"""
Small shared utilities that don't belong to any single agent.
"""

from config import KNOWLEDGE_BASE_PATH


def read_knowledge_base() -> str:
    """Load the DQ checks knowledge base used by the Rule Creator agent."""
    return KNOWLEDGE_BASE_PATH.read_text()