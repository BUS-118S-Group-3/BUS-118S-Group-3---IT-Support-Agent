"""MCP server exposing the Access Provisioning system as standard MCP tools.

Run with:
    python mcp_server.py            # stdio transport (Claude Desktop, etc.)

Or wire it into Claude Desktop's claude_desktop_config.json (see
docs/MCP_SETUP.md for the exact config snippet).

Tools exposed:
  - request_access            : run the multi-agent flow on a free-text request
  - lookup_user               : inspect a user record
  - lookup_group              : inspect an AD group / folder
  - list_groups               : enumerate all known groups
  - list_pending_escalations  : queue of tickets awaiting a human
  - approve_escalation        : human approves a pending ticket → grants AD
  - deny_escalation           : human denies a pending ticket
  - reassign_escalation       : bounce a ticket to a different human
  - read_audit_log            : tail of audit events
  - dashboard_stats           : aggregate counters

Why expose it as MCP?  Lets the same logic drive the Streamlit UI AND
be called from any MCP client (Claude Desktop, VS Code with Continue,
the Anthropic API with mcp-remote, etc.) without copy-pasted code.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Make sure the project root is on sys.path when launched from anywhere
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP

from agents import admin_actions
from agents.orchestrator import run as run_graph
from integrations import active_directory as ad
from integrations import jira_client as jira
from integrations.audit_log import read_recent

mcp = FastMCP("access-provisioning")


# ---------------------------------------------------------------------------
# End-user-facing tools
# ---------------------------------------------------------------------------

@mcp.tool()
def request_access(message: str, requester_email: str) -> dict[str, Any]:
    """Submit a free-text access request and run it through the agent graph.

    Args:
        message: What the user wants, in plain English.
                 e.g. "I need access to Marketing-Public for a campaign launch"
        requester_email: Email of the user the request is on behalf of.

    Returns the final state including decision, citations, ticket key,
    and the user-facing reply.
    """
    state = run_graph(message, requester_email=requester_email)
    return {
        "decision": state.get("decision"),
        "risk_tier": state.get("risk_tier"),
        "rationale": state.get("decision_rationale"),
        "citations": state.get("citations") or [],
        "ticket_key": state.get("ticket_key"),
        "ad_changed": state.get("ad_changed"),
        "reply": state.get("final_response"),
    }


@mcp.tool()
def lookup_user(email: str) -> dict[str, Any]:
    """Get a user's HR record (department, employee type, training status,
    current group memberships, recent revocations)."""
    try:
        u = ad.get_user(email)
    except ad.ADError as exc:
        return {"error": str(exc)}
    u["current_groups"] = ad.user_groups(email)
    return u


@mcp.tool()
def lookup_group(name: str) -> dict[str, Any]:
    """Get a group/folder's catalog entry (risk tier, owner, allowed
    departments, current members)."""
    try:
        return ad.get_group(name)
    except ad.ADError as exc:
        return {"error": str(exc)}


@mcp.tool()
def list_groups() -> list[str]:
    """List every known AD group / shared folder."""
    return ad.list_groups()


# ---------------------------------------------------------------------------
# Admin-facing tools (human-in-the-loop)
# ---------------------------------------------------------------------------

@mcp.tool()
def list_pending_escalations(limit: int = 20) -> list[dict[str, Any]]:
    """Tickets that the agent escalated and are awaiting a human decision.

    Each entry has the original request context, the Knowledge Agent's
    rationale, citations, and routing info — enough to decide without
    going to another system.
    """
    out = []
    for t in admin_actions.list_pending_escalations(limit=limit):
        f = t["fields"]
        md = t.get("metadata") or {}
        out.append({
            "key": t["key"],
            "summary": f["summary"],
            "priority": f["priority"]["name"],
            "status": f["status"]["name"],
            "assignee": f["assignee"]["emailAddress"],
            "decision": md.get("decision"),
            "risk_tier": md.get("risk_tier"),
            "requester": md.get("requester_email"),
            "resource": md.get("target_resource"),
            "rationale": md.get("rationale"),
            "citations": md.get("citations") or [],
            "user_message": md.get("user_message"),
            "sla": md.get("sla"),
            "updated": f.get("updated"),
        })
    return out


@mcp.tool()
def approve_escalation(
    ticket_key: str,
    approver_email: str,
    note: str = "",
) -> dict[str, Any]:
    """Approve a pending escalation. Executes the AD grant and closes the ticket.

    Args:
        ticket_key: e.g. "ITACCESS-12"
        approver_email: who is approving (recorded in audit log)
        note: optional free-text note attached to the ticket
    """
    try:
        return admin_actions.approve_escalation(ticket_key, approver_email, note).to_dict()
    except admin_actions.AdminActionError as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def deny_escalation(
    ticket_key: str,
    approver_email: str,
    note: str = "",
) -> dict[str, Any]:
    """Deny a pending escalation. No AD change. Records the reason."""
    try:
        return admin_actions.deny_escalation(ticket_key, approver_email, note).to_dict()
    except admin_actions.AdminActionError as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def reassign_escalation(
    ticket_key: str,
    new_assignee_email: str,
    actor_email: str,
    note: str = "",
) -> dict[str, Any]:
    """Reassign a pending escalation to a different human owner."""
    try:
        return admin_actions.reassign_escalation(
            ticket_key, new_assignee_email, actor_email, note
        ).to_dict()
    except admin_actions.AdminActionError as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------

@mcp.tool()
def read_audit_log(limit: int = 25) -> list[dict[str, Any]]:
    """Most recent audit events, newest first."""
    return read_recent(limit=limit)


@mcp.tool()
def dashboard_stats() -> dict[str, Any]:
    """Aggregate counters: total requests, auto-resolution rate, queue depth."""
    return admin_actions.stats()


@mcp.tool()
def get_ticket(key: str) -> dict[str, Any]:
    """Fetch the full ticket record by key."""
    t = jira.get_ticket(key)
    return t or {"error": f"Ticket not found: {key}"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # FastMCP defaults to stdio, which is what Claude Desktop expects.
    mcp.run()
