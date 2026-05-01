"""Workflow Agent.

When the Knowledge Agent says "auto_approve", the Workflow Agent does the
actual work: add to the AD group, log the audit event, file an
informational ticket so there is a paper trail, and draft the user reply.
"""

from __future__ import annotations

from agents.state import GraphState, TraceStep
from integrations import active_directory as ad
from integrations import jira_client as jira
from integrations.audit_log import log_event


def _expiry_days(risk_tier: str) -> int | None:
    return {"low": None, "medium": 90, "high": 30, "restricted": 7}.get(risk_tier)


def run(state: GraphState) -> GraphState:
    intake = state.get("intake") or {}
    email = intake.get("requester_email") or ""
    target = intake.get("target_resource") or ""
    risk_tier = state.get("risk_tier") or "unknown"

    # Defensive — should never get here without these
    if not email or not target:
        msg = "Workflow refused: missing requester or target."
        log_event("workflow_skipped", {"reason": msg, "intake": dict(intake)})
        return {
            "action_taken": msg,
            "ad_changed": False,
            "final_response": (
                "I tried to provision access automatically but couldn't because "
                "the request is missing the requester identity or the target group. "
                "Please re-submit with both."
            ),
            "trace": [TraceStep(agent="Workflow", summary="skipped — missing fields")],
        }

    # 1. Apply the AD change (idempotent)
    try:
        ad.add_user_to_group(email, target)
    except ad.ADError as exc:
        log_event("workflow_error", {"error": str(exc), "email": email, "target": target})
        return {
            "action_taken": f"AD update failed: {exc}",
            "ad_changed": False,
            "final_response": (
                f"I couldn't grant '{target}' to {email}: {exc}. "
                "I've logged the failure; a human will follow up."
            ),
            "trace": [TraceStep(agent="Workflow", summary=f"failure: {exc}")],
        }

    # 2. Informational Jira ticket so the audit trail is visible to humans
    expiry = _expiry_days(risk_tier)
    expiry_line = f"Time-bound: {expiry} days." if expiry else "No expiry (low-risk)."
    ticket = jira.create_ticket(
        summary=f"[Auto-Granted] {email} → {target}",
        description=(
            f"Auto-approved by the Workflow Agent.\n\n"
            f"Requester: {email}\n"
            f"Group: {target}\n"
            f"Risk tier: {risk_tier}\n"
            f"Justification: {intake.get('justification') or '(low-risk; not required)'}\n"
            f"Knowledge rationale: {state.get('decision_rationale','')}\n"
            f"Citations: {', '.join(state.get('citations', []))}\n"
            f"{expiry_line}\n"
        ),
        assignee="it-helpdesk@acme.example",
        priority="P4",
        labels=["access-request", "auto-approved", risk_tier],
        status="Granted",
        metadata={
            "kind": "auto_grant",
            "decision": "auto_approve",
            "requester_email": email,
            "target_resource": target,
            "risk_tier": risk_tier,
            "requested_action": "grant",
            "justification": intake.get("justification") or "",
            "rationale": state.get("decision_rationale") or "",
            "citations": state.get("citations") or [],
            "expiry_days": expiry,
        },
    )

    log_event("workflow_grant", {
        "email": email,
        "target": target,
        "risk_tier": risk_tier,
        "ticket_key": ticket["key"],
    })

    body_lines = [
        f"Done — {email} has been added to **{target}**.",
        "",
        f"- Risk tier: {risk_tier}",
        f"- Audit ticket: {ticket['key']}",
    ]
    if expiry:
        body_lines.append(f"- Expires in {expiry} days; you'll get a re-justification reminder.")
    if state.get("citations"):
        body_lines.append(f"- Policy basis: {', '.join(state['citations'])}")
    final = "\n".join(body_lines)

    return {
        "action_taken": f"Granted {target} to {email}; ticket {ticket['key']}",
        "ad_changed": True,
        "ticket_key": ticket["key"],
        "final_response": final,
        "trace": [TraceStep(
            agent="Workflow",
            summary=f"granted {target} → {email}; {ticket['key']}",
            detail={"ticket": ticket["key"], "risk_tier": risk_tier},
        )],
    }
