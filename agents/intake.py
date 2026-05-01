"""Intake Agent.

Job: convert a free-text request into structured fields the rest of the
graph can act on. We do *not* make any access decision here — the
Intake Agent is intentionally narrow so failures don't cascade.
"""

from __future__ import annotations

from agents._llm import call_json
from agents.state import GraphState, IntakeFields, TraceStep
from integrations import active_directory as ad
from integrations.audit_log import log_event


_SYSTEM = """You are the Intake Agent in an IT access provisioning system.

Your only job is to read a user's request and emit a single JSON object with
these fields:

{
  "requester_email": "<email if user mentioned themselves, else empty>",
  "requested_action": "grant" | "revoke" | "unknown",
  "target_resource": "<best guess at the AD group or shared folder name>",
  "justification": "<the user's stated business reason, verbatim or paraphrased; empty if absent>",
  "urgency": "normal" | "blocked" | "urgent",
  "confidence": 0.0,
  "notes": "<one short line about ambiguity or missing info>"
}

Guidance:
- Map informal names to the canonical group from this list when obvious:
  KNOWN_GROUPS_PLACEHOLDER
- "I'm blocked", "deadline today", "can't work" → urgency = "blocked".
- "Outage", "production down", "P1" → urgency = "urgent".
- If the resource is genuinely unclear, set target_resource to the user's
  literal phrase and lower confidence below 0.5.
- Output JSON only. No prose, no markdown fences.
"""


def _system_prompt() -> str:
    groups = ad.list_groups()
    return _SYSTEM.replace("KNOWN_GROUPS_PLACEHOLDER", ", ".join(groups))


def run(state: GraphState) -> GraphState:
    user_msg = state.get("user_message", "")
    hint_email = state.get("requester_email_hint", "")

    user_prompt = f"User request:\n{user_msg!r}\n"
    if hint_email:
        user_prompt += f"\nSession identity (use as requester_email if not contradicted): {hint_email}\n"

    try:
        raw = call_json(_system_prompt(), user_prompt)
    except Exception as exc:  # pragma: no cover -- network/model errors
        log_event("intake_error", {"message": user_msg, "error": str(exc)})
        return {
            "intake": {
                "requester_email": hint_email,
                "requested_action": "unknown",
                "target_resource": "",
                "justification": "",
                "urgency": "normal",
                "confidence": 0.0,
                "notes": f"intake_error: {exc}",
            },
            "trace": [TraceStep(agent="Intake", summary=f"failed: {exc}")],
            "error": f"Intake failed: {exc}",
        }

    fields: IntakeFields = {
        "requester_email": (raw.get("requester_email") or hint_email or "").strip(),
        "requester_name": "",
        "requested_action": raw.get("requested_action") or "unknown",
        "target_resource": (raw.get("target_resource") or "").strip(),
        "justification": (raw.get("justification") or "").strip(),
        "urgency": raw.get("urgency") or "normal",
        "confidence": float(raw.get("confidence") or 0.0),
        "notes": (raw.get("notes") or "").strip(),
    }

    # Try to enrich with the user record if we have an email
    if fields["requester_email"]:
        try:
            user = ad.get_user(fields["requester_email"])
            fields["requester_name"] = user.get("name", "")
        except ad.ADError:
            pass

    log_event("intake", {"input": user_msg, "extracted": dict(fields)})

    summary = (
        f"action={fields['requested_action']} target={fields['target_resource'] or '?'} "
        f"urgency={fields['urgency']} confidence={fields['confidence']:.2f}"
    )
    return {
        "intake": fields,
        "trace": [TraceStep(agent="Intake", summary=summary, detail=dict(fields))],
    }
