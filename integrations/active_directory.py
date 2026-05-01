"""Mock Active Directory adapter.

State is persisted to ``data/users.json`` and ``data/groups.json``. The
public interface (``get_user``, ``get_group``, ``add_user_to_group``,
``remove_user_from_group``, ``user_groups``) is intentionally narrow so
that swapping in a real ``ldap3``/``msgraph`` client only requires
re-implementing this module.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings


class ADError(Exception):
    """Raised on adapter-level failures (user not found, group not found)."""


class _JsonStore:
    """Tiny JSON-on-disk store with a process-local lock."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def read(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.exists():
                return {}
            return json.loads(self.path.read_text(encoding="utf-8"))

    def write(self, data: dict[str, Any]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )


_users = _JsonStore(settings.data_dir / "users.json")
_groups = _JsonStore(settings.data_dir / "groups.json")


# ---------- Reads ----------

def get_user(email: str) -> dict[str, Any]:
    users = _users.read()
    if email not in users:
        raise ADError(f"User not found: {email}")
    return {"email": email, **users[email]}


def get_group(name: str) -> dict[str, Any]:
    groups = _groups.read()
    if name not in groups:
        raise ADError(f"Group not found: {name}")
    return {"name": name, **groups[name]}


def list_groups() -> list[str]:
    return sorted(_groups.read().keys())


def list_users() -> list[str]:
    return sorted(_users.read().keys())


def user_groups(email: str) -> list[str]:
    """All groups a user is currently a member of."""
    groups = _groups.read()
    return sorted(g for g, info in groups.items() if email in info.get("members", []))


# ---------- Writes ----------

def add_user_to_group(email: str, group_name: str) -> dict[str, Any]:
    """Idempotent membership add. Returns the new group state."""
    groups = _groups.read()
    if group_name not in groups:
        raise ADError(f"Group not found: {group_name}")
    members = groups[group_name].setdefault("members", [])
    if email not in members:
        members.append(email)
    _groups.write(groups)
    return {"name": group_name, **groups[group_name]}


def remove_user_from_group(email: str, group_name: str) -> dict[str, Any]:
    groups = _groups.read()
    if group_name not in groups:
        raise ADError(f"Group not found: {group_name}")
    members = groups[group_name].get("members", [])
    if email in members:
        members.remove(email)
    _groups.write(groups)
    return {"name": group_name, **groups[group_name]}


# ---------- Convenience checks used by the agents ----------

def would_create_sod_violation(email: str, target_group: str) -> tuple[bool, list[str]]:
    """Return (violates, conflicting_existing_groups).

    The exclusion relation is treated as symmetric: it fires if either the
    target's catalog entry lists a conflict the user already holds, OR any
    group the user currently holds lists the target as a conflict. This way
    we don't depend on the JSON having the relation declared on both sides.
    """
    groups = _groups.read()
    if target_group not in groups:
        raise ADError(f"Group not found: {target_group}")

    target_excludes: set[str] = set(groups[target_group].get("mutually_exclusive_with", []) or [])
    held = set(user_groups(email))

    forward = target_excludes & held
    reverse = {
        g for g in held
        if target_group in (groups.get(g, {}).get("mutually_exclusive_with", []) or [])
    }
    overlap = sorted(forward | reverse)
    return bool(overlap), overlap


def is_recently_revoked(email: str, group_name: str, days: int = 30) -> bool:
    user = get_user(email)
    revocations = user.get("recently_revoked", []) or []
    if not revocations:
        return False
    now = datetime.now(timezone.utc)
    for r in revocations:
        if r.get("group") != group_name:
            continue
        try:
            d = datetime.fromisoformat(r["date"]).replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if (now - d).days <= days and r.get("reason") == "for_cause":
            return True
    return False
