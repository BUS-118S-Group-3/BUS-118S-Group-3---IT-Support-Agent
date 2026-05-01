"""Mock Jira adapter.

Persists tickets to ``data/tickets.json``. Returns shapes that match the
real Jira REST API for ``POST /rest/api/3/issue`` and the issue search
endpoint, so a real adapter can drop in without changing callers.

Beyond plain create/list, this version also supports:

- ``metadata`` on tickets (a structured dict that the Escalation Agent
  populates so admin tools can act without scraping the description text)
- ``transition_ticket`` to move a ticket between statuses, with an
  audit-friendly comment trail.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from config import settings

_TICKETS_PATH = settings.data_dir / "tickets.json"
_lock = threading.Lock()

OPEN_STATUSES: set[str] = {"Open", "In Review", "Pending Approval"}
CLOSED_STATUSES: set[str] = {"Resolved", "Granted", "Denied", "Cancelled"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read() -> dict[str, Any]:
    if not _TICKETS_PATH.exists():
        return {"tickets": []}
    return json.loads(_TICKETS_PATH.read_text(encoding="utf-8"))


def _write(data: dict[str, Any]) -> None:
    _TICKETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _TICKETS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ---------- Create ----------

def create_ticket(
    *,
    summary: str,
    description: str,
    assignee: str,
    priority: str = "P3",
    labels: list[str] | None = None,
    project_key: str = "ITACCESS",
    status: str = "Open",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a ticket and return the API-shaped record."""
    with _lock:
        data = _read()
        seq = len(data["tickets"]) + 1
        key = f"{project_key}-{seq}"
        ticket = {
            "id": str(uuid.uuid4()),
            "key": key,
            "fields": {
                "summary": summary,
                "description": description,
                "assignee": {"emailAddress": assignee},
                "priority": {"name": priority},
                "labels": labels or [],
                "status": {"name": status},
                "created": _now(),
                "updated": _now(),
                "comments": [],
            },
            "metadata": metadata or {},
        }
        data["tickets"].append(ticket)
        _write(data)
        return ticket


# ---------- Read ----------

def list_tickets(limit: int = 50) -> list[dict[str, Any]]:
    """Most recent first."""
    return list(reversed(_read()["tickets"]))[:limit]


def list_open_tickets(limit: int = 100) -> list[dict[str, Any]]:
    """Tickets that still need attention (Open / In Review / Pending Approval)."""
    out = []
    for t in reversed(_read()["tickets"]):
        if t["fields"]["status"]["name"] in OPEN_STATUSES:
            out.append(t)
        if len(out) >= limit:
            break
    return out


def get_ticket(key: str) -> dict[str, Any] | None:
    for t in _read()["tickets"]:
        if t["key"] == key:
            return t
    return None


# ---------- Update ----------

def transition_ticket(
    key: str,
    *,
    new_status: str,
    actor: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Move a ticket to a new status and append a comment with the actor's note.

    Raises KeyError if the ticket doesn't exist or the status is invalid.
    """
    if new_status not in OPEN_STATUSES | CLOSED_STATUSES:
        raise ValueError(f"Unknown status: {new_status}")

    with _lock:
        data = _read()
        for t in data["tickets"]:
            if t["key"] != key:
                continue
            old = t["fields"]["status"]["name"]
            t["fields"]["status"]["name"] = new_status
            t["fields"]["updated"] = _now()
            t["fields"].setdefault("comments", []).append({
                "ts": _now(),
                "actor": actor,
                "from": old,
                "to": new_status,
                "note": note or "",
            })
            _write(data)
            return t
        raise KeyError(f"Ticket not found: {key}")


def add_comment(key: str, *, actor: str, note: str) -> dict[str, Any]:
    """Append a free-text comment without changing status."""
    with _lock:
        data = _read()
        for t in data["tickets"]:
            if t["key"] != key:
                continue
            t["fields"].setdefault("comments", []).append({
                "ts": _now(),
                "actor": actor,
                "note": note,
            })
            t["fields"]["updated"] = _now()
            _write(data)
            return t
        raise KeyError(f"Ticket not found: {key}")
