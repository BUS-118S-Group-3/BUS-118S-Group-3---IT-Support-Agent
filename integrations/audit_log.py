"""Append-only JSONL audit log.

Every state transition in the multi-agent graph records an event here.
The compliance team can replay any decision: input request, retrieved
chunks, agent recommendation, action taken.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any

from config import settings

_lock = threading.Lock()


def log_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Append an event and return it."""
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "payload": payload,
    }
    with _lock:
        settings.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        with settings.audit_log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def read_recent(limit: int = 50) -> list[dict[str, Any]]:
    if not settings.audit_log_path.exists():
        return []
    with settings.audit_log_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    out: list[dict[str, Any]] = []
    for line in reversed(lines[-limit:]):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
