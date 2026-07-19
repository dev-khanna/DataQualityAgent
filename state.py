"""
state.py

Shared graph state. Every agent in this project runs on the same minimal
state: a single running message timeline.
"""

from typing import TypedDict, Annotated, List

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]