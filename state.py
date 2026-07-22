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

# Resolved: yes, messages are being saved/accumulated correctly here - the
# `add_messages` reducer appends each new message to the list instead of
# overwriting it, which is the standard LangGraph pattern for a running
# conversation. In practice this file isn't wired into the agents directly:
# create_agent() (used in agents/individual_table_dq_agent.py) already
# builds an equivalent state schema for you, and TodoListMiddleware extends
# it with its own `todos` field automatically. This class is kept around in
# case a future agent needs a plain, custom state instead of create_agent's
# default.
