"""LangGraph orchestrator.

Graph shape:

    START → intake → knowledge → router(decision) ─┬─ workflow   → END
                                                   └─ escalation → END
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langgraph.graph import END, StateGraph

from agents import escalation, intake, knowledge, workflow
from agents.state import GraphState
from integrations.audit_log import log_event


def _route_after_knowledge(state: GraphState) -> str:
    decision = state.get("decision", "needs_review")
    if decision == "auto_approve":
        return "workflow"
    return "escalation"


@lru_cache(maxsize=1)
def build_graph():
    g = StateGraph(GraphState)
    g.add_node("intake", intake.run)
    g.add_node("knowledge", knowledge.run)
    g.add_node("workflow", workflow.run)
    g.add_node("escalation", escalation.run)

    g.set_entry_point("intake")
    g.add_edge("intake", "knowledge")
    g.add_conditional_edges(
        "knowledge",
        _route_after_knowledge,
        {"workflow": "workflow", "escalation": "escalation"},
    )
    g.add_edge("workflow", END)
    g.add_edge("escalation", END)
    return g.compile()


def run(user_message: str, requester_email: str | None = None) -> dict[str, Any]:
    """Execute the full graph for a single user message and return the final state."""
    graph = build_graph()
    initial: GraphState = {
        "user_message": user_message,
        "requester_email_hint": requester_email or "",
        "trace": [],
    }
    log_event("request_received", {
        "message": user_message,
        "requester_hint": requester_email or "",
    })
    final = graph.invoke(initial)
    log_event("request_completed", {
        "decision": final.get("decision"),
        "action_taken": final.get("action_taken"),
        "ticket_key": final.get("ticket_key"),
    })
    return dict(final)
