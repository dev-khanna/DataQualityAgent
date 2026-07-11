"""
Builds the supervisor graph.

Every worker connects only to the orchestrator - never to each other.
The orchestrator decides where to go next after every single step, and
every worker's only outgoing edge leads straight back to it.
"""

from langgraph.graph import END, StateGraph

from agents.database_agent import database_agent_node
from agents.orchestrator import orchestrator_node
from agents.rule_creator import rule_creator_node
from agents.sql_generator import sql_generator_node
from nodes.executor import sql_executor_node
from nodes.report_writer import report_writer_node
from nodes.validator import sql_validator_node
from state import DQState

WORKER_NODES = {
    "database_intelligence": database_agent_node,
    "rule_creator": rule_creator_node,
    "sql_generator": sql_generator_node,
    "sql_validator": sql_validator_node,
    "sql_executor": sql_executor_node,
    "report_writer": report_writer_node,
}


def route_from_orchestrator(state: DQState) -> str:
    return state["next_agent"]


def build_graph():
    graph = StateGraph(DQState)

    graph.add_node("orchestrator", orchestrator_node)
    for name, node_fn in WORKER_NODES.items():
        graph.add_node(name, node_fn)

    graph.set_entry_point("orchestrator")

    graph.add_conditional_edges(
        "orchestrator",
        route_from_orchestrator,
        {**{name: name for name in WORKER_NODES}, "finished": END},
    )

    # Every worker always hands control straight back to the orchestrator.
    for name in WORKER_NODES:
        graph.add_edge(name, "orchestrator")

    return graph.compile()