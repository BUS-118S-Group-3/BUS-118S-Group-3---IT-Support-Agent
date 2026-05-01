"""Escalation Agent.

Two flavors:
  - decision = "needs_review" → file a routed Jira ticket and explain.
  - decision = "deny"          → write a polite, policy-grounded denial
                                 and file a record (no AD change).

The routing matrix lives in escalation_runbook.md and is encoded here.
"""

from __future__ import annotations

from agents._llm import call_text
from agents.state import GraphState, TraceStep
from integrations import active_directory as ad
from integrations import jira_client as jira
from integrations.audit_log import log_event


def _route(state: GraphState) -> tuple[str, str]:
    """Return (assignee_email, priority) per the runbook."""
    intake = state.get("intake") or {}
    risk = state.get("risk_tier") or "unknown"
    rationale = (state.get("decision_rationale") or "").lower()
    urgency = intake.get("urgency", "normal")
    target = intake.get("target_resource") or ""

    # Priority follows urgency
    priority = "P3"
    if urgency == "blocked":
        priority = "P2"
    if urgency == "urgent":
        priority = "P1"

    # Compliance-routed cases
    if "separation-of-duties" in rationale or "sox" in rationale:
        return "compliance@acme.example", priority
    if "contractor" in rationale and "employees-only" in rationale:
        return "compliance@acme.example", priority
    if "revoked" in rationale and "30 days" in rationale:
        return "compliance@acme.example", priority
    if risk == "restricted":
        return "compliance@acme.example", priority

    # Manager + data owner for high
    if risk == "high":
        try:
            owner = ad.get_group(target).get("data_owner", "it-helpdesk@acme.example")
        except ad.ADError:
            owner = "it-helpdesk@acme.example"
        return owner, priority

    # Manager for medium / unknown
    email = intake.get("requester_email") or ""
    if email:
        try:
            mgr = ad.get_user(email).get("manager")
            if mgr:
                return mgr, priority
        except ad.ADError:
            pass

    return "it-helpdesk@acme.example", priority


def _draft_user_reply(state: GraphState, ticket_key: str, assignee: str, sla: str) -> str:
    """Use the LLM to write a clear, non-hedging user-facing reply.
    Fall back to a templated reply if the LLM call fails."""
    decision = state.get("decision", "needs_review")
    intake = state.get("intake") or {}
    rationale = state.get("decision_rationale") or ""
    citations = state.get("citations") or []

    system = (
        "You write user-facing IT support replies. Be direct and warm. "
        "Do NOT hedge ('the system thinks', 'probably'). "
        "Always: (1) acknowledge the request, (2) state exactly why it wasn't auto-fulfilled "
        "with the policy citations, (3) name who owns it now and the SLA, "
        "(4) tell the user what to do next. 80-150 words. No emojis."
    )
    user = (
        f"Decision: {decision}\n"
        f"Requested resource: {intake.get('target_resource')}\n"
        f"Requester: {intake.get('requester_email')}\n"
        f"Rationale: {rationale}\n"
        f"Citations: {', '.join(citations) or '(none)'}\n"
        f"Ticket: {ticket_key}\n"
        f"Assignee: {assignee}\n"
        f"SLA: {sla}\n"
    )

    try:
        return call_text(system, user)
    except Exception:
        # deterministic fallback
        verb = "denied per policy" if decision == "deny" else "routed for review"
        cite = f" ({'; '.join(citations)})" if citations else ""
        return (
            f"Your request has been received and {verb}.{cite} "
            f"Reason: {rationale} "
            f"Tracking ticket: {ticket_key} (assignee: {assignee}, SLA: {sla}). "
            f"You don't need to do anything else; the assignee will reach out if more info is needed."
        )


def run(state: GraphState) -> GraphState:
    decision = state.get("decision", "needs_review")
    intake = state.get("intake") or {}
    target = intake.get("target_resource") or "(unspecified)"
    email = intake.get("requester_email") or "(unknown)"

    assignee, priority = _route(state)
    sla = {"P1": "1h", "P2": "4h", "P3": "8h"}.get(priority, "24h")

    summary_prefix = "[Access Denied]" if decision == "deny" else "[Access Review]"
    risk = state.get("risk_tier") or "unknown"
    summary = f"{summary_prefix} {email} → {target} ({risk})"

    description_lines = [
        f"User message: {state.get('user_message','')!r}",
        "",
        f"Requester: {email}",
        f"Resource: {target}",
        f"Risk tier: {risk}",
        f"Action requested: {intake.get('requested_action')}",
        f"Justification: {intake.get('justification') or '(none)'}",
        f"Urgency: {intake.get('urgency')}",
        "",
        "Knowledge Agent recommendation:",
        f"  decision: {decision}",
        f"  rationale: {state.get('decision_rationale','')}",
        f"  citations: {', '.join(state.get('citations', [])) or '(none)'}",
        "",
        f"Routing: {assignee} (priority {priority}, SLA {sla})",
    ]

    labels = ["access-request", "auto-routed", risk]
    if decision == "deny":
        labels.append("denied")

    metadata = {
        "kind": "escalation",
        "decision": decision,
        "requester_email": email,
        "target_resource": target,
        "risk_tier": risk,
        "requested_action": intake.get("requested_action") or "grant",
        "justification": intake.get("justification") or "",
        "urgency": intake.get("urgency") or "normal",
        "rationale": state.get("decision_rationale") or "",
        "citations": state.get("citations") or [],
        "user_message": state.get("user_message") or "",
        "sla": sla,
    }

    ticket = jira.create_ticket(
        summary=summary,
        description="\n".join(description_lines),
        assignee=assignee,
        priority=priority,
        labels=labels,
        metadata=metadata,
    )

    log_event("escalation", {
        "decision": decision,
        "email": email,
        "target": target,
        "risk_tier": risk,
        "ticket_key": ticket["key"],
        "assignee": assignee,
        "priority": priority,
    })

    user_reply = _draft_user_reply(state, ticket["key"], assignee, sla)

    return {
        "action_taken": f"{summary_prefix} ticket {ticket['key']} → {assignee}",
        "ad_changed": False,
        "ticket_key": ticket["key"],
        "final_response": user_reply,
        "trace": [TraceStep(
            agent="Escalation",
            summary=f"{decision} → {assignee} as {ticket['key']} ({priority})",
            detail={
                "ticket": ticket["key"],
                "assignee": assignee,
                "priority": priority,
                "sla": sla,
            },
        )],
    }
