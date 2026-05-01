"""The shared state object that flows through every node in the LangGraph.

LangGraph reducers: each field is replaced wholesale unless we annotate
it differently. ``trace`` accumulates so we can render the agent path in
the UI sidebar.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict, NotRequired


Decision = Literal["auto_approve", "needs_review", "deny", "unknown"]


class IntakeFields(TypedDict, total=False):
    requester_email: str
    requester_name: str
    target_resource: str          # group/folder name as best identified
    requested_action: Literal["grant", "revoke", "unknown"]
    justification: str
    urgency: Literal["normal", "blocked", "urgent"]
    confidence: float             # 0..1, how confident the Intake agent is
    notes: str


class TraceStep(TypedDict):
    agent: str
    summary: str
    detail: NotRequired[dict[str, Any]]


class GraphState(TypedDict, total=False):
    # Inputs
    user_message: str
    requester_email_hint: str        # passed in from the UI session

    # Intake
    intake: IntakeFields

    # Knowledge
    retrieved_chunks: list[dict[str, Any]]   # serialized RetrievedChunk
    decision: Decision
    decision_rationale: str
    citations: list[str]
    risk_tier: Literal["low", "medium", "high", "restricted", "unknown"]

    # Workflow / Escalation outputs
    action_taken: str                # human-readable summary
    ticket_key: str                  # set if escalated
    ad_changed: bool

    # Final user-facing reply
    final_response: str

    # Observability — accumulates across nodes
    trace: Annotated[list[TraceStep], operator.add]

    # Errors
    error: str
