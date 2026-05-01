"""Human-in-the-loop actions invoked from the admin dashboard or MCP.

When the Knowledge Agent routes a request to ``needs_review``, the
ticket sits in the queue waiting on a human. The admin can then:

  - approve_escalation()  → execute the AD grant, mark ticket Granted
  - deny_escalation()     → mark ticket Denied (no AD change)
  - reassign_escalation() → bounce to a different human

Each action is idempotent: re-approving an already-approved ticket
short-circuits and just returns the existing state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from integrations import active_directory as ad
from integrations import jira_client as jira
from integrations.audit_log import log_event


class AdminActionError(Exception):
    """Raised when the admin tried to act on a ticket that can't be acted on."""


@dataclass
class ActionResult:
    ok: bool
    ticket_key: str
    new_status: str
    message: str
    ad_changed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "ticket_key": self.ticket_key,
            "new_status": self.new_status,
            "message": self.message,
            "ad_changed": self.ad_changed,
        }


def _load_actionable(ticket_key: str) -> dict[str, Any]:
    t = jira.get_ticket(ticket_key)
    if t is None:
        raise AdminActionError(f"Ticket {ticket_key} not found.")
    md = t.get("metadata") or {}
    if md.get("kind") != "escalation":
        raise AdminActionError(
            f"Ticket {ticket_key} is not an escalation "
            f"(kind={md.get('kind')!r}); admin actions don't apply."
        )
    return t


def list_pending_escalations(limit: int = 50) -> list[dict[str, Any]]:
    """All escalation tickets still awaiting a human decision."""
    out: list[dict[str, Any]] = []
    for t in jira.list_open_tickets(limit=limit * 2):
        md = t.get("metadata") or {}
        if md.get("kind") == "escalation":
            out.append(t)
        if len(out) >= limit:
            break
    return out


def approve_escalation(
    ticket_key: str,
    approver: str,
    note: str = "",
) -> ActionResult:
    """Approve a pending escalation: execute the AD grant and close the ticket.

    Idempotent — re-approving an already-Granted ticket is a no-op that
    returns the existing state.
    """
    t = _load_actionable(ticket_key)
    md = t["metadata"]
    status = t["fields"]["status"]["name"]

    # Idempotency
    if status in {"Granted", "Resolved"}:
        return ActionResult(
            ok=True, ticket_key=ticket_key, new_status=status,
            message=f"Already {status.lower()}; nothing to do.", ad_changed=False,
        )
    if status == "Denied":
        raise AdminActionError(
            f"Ticket {ticket_key} was previously Denied; reopen it first if you want to approve."
        )

    requester = md.get("requester_email")
    target = md.get("target_resource")
    if not requester or not target:
        raise AdminActionError(
            f"Ticket {ticket_key} is missing requester or target in its metadata; "
            "cannot execute the grant automatically."
        )

    # Execute the AD change
    try:
        ad.add_user_to_group(requester, target)
        ad_changed = True
    except ad.ADError as exc:
        log_event("admin_action_error", {
            "ticket_key": ticket_key, "approver": approver, "error": str(exc),
            "phase": "ad_grant",
        })
        raise AdminActionError(f"AD grant failed: {exc}")

    # Update the ticket
    full_note = f"Approved by {approver}." + (f" Note: {note}" if note else "")
    jira.transition_ticket(ticket_key, new_status="Granted", actor=approver, note=full_note)

    log_event("admin_approved", {
        "ticket_key": ticket_key,
        "approver": approver,
        "requester": requester,
        "target": target,
        "note": note,
    })

    return ActionResult(
        ok=True, ticket_key=ticket_key, new_status="Granted",
        message=f"Granted {target} to {requester}.", ad_changed=ad_changed,
    )


def deny_escalation(
    ticket_key: str,
    approver: str,
    note: str = "",
) -> ActionResult:
    """Deny a pending escalation. No AD change."""
    t = _load_actionable(ticket_key)
    status = t["fields"]["status"]["name"]

    if status == "Denied":
        return ActionResult(
            ok=True, ticket_key=ticket_key, new_status=status,
            message="Already denied; nothing to do.", ad_changed=False,
        )
    if status in {"Granted", "Resolved"}:
        raise AdminActionError(
            f"Ticket {ticket_key} is {status}; can't be denied without revoking the grant first."
        )

    md = t["metadata"]
    full_note = f"Denied by {approver}." + (f" Reason: {note}" if note else "")
    jira.transition_ticket(ticket_key, new_status="Denied", actor=approver, note=full_note)

    log_event("admin_denied", {
        "ticket_key": ticket_key,
        "approver": approver,
        "requester": md.get("requester_email"),
        "target": md.get("target_resource"),
        "note": note,
    })

    return ActionResult(
        ok=True, ticket_key=ticket_key, new_status="Denied",
        message="Request denied; no AD change.",
    )


def reassign_escalation(
    ticket_key: str,
    new_assignee: str,
    actor: str,
    note: str = "",
) -> ActionResult:
    """Bounce a ticket to a different human."""
    t = _load_actionable(ticket_key)
    full_note = f"Reassigned by {actor} from {t['fields']['assignee']['emailAddress']} to {new_assignee}."
    if note:
        full_note += f" {note}"

    # We don't have a real assignee setter; piggy-back on add_comment + edit
    t["fields"]["assignee"]["emailAddress"] = new_assignee
    jira.add_comment(ticket_key, actor=actor, note=full_note)

    log_event("admin_reassigned", {
        "ticket_key": ticket_key,
        "actor": actor,
        "new_assignee": new_assignee,
        "note": note,
    })

    return ActionResult(
        ok=True, ticket_key=ticket_key,
        new_status=t["fields"]["status"]["name"],
        message=f"Reassigned to {new_assignee}.",
    )


def stats() -> dict[str, Any]:
    """Aggregate stats for the admin dashboard summary."""
    tickets = jira.list_tickets(limit=10_000)
    by_status: dict[str, int] = {}
    by_decision: dict[str, int] = {}
    for t in tickets:
        s = t["fields"]["status"]["name"]
        by_status[s] = by_status.get(s, 0) + 1
        d = (t.get("metadata") or {}).get("decision", "unknown")
        by_decision[d] = by_decision.get(d, 0) + 1
    total = len(tickets)
    auto = by_decision.get("auto_approve", 0)
    return {
        "total_requests": total,
        "auto_resolution_rate": (auto / total) if total else 0.0,
        "by_status": by_status,
        "by_decision": by_decision,
        "pending_escalations": len(list_pending_escalations()),
    }
