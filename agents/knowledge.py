"""Knowledge Agent.

Pulls policy chunks from ChromaDB, then asks the LLM to make a *grounded*
recommendation: auto_approve | needs_review | deny. The LLM is told it
MAY only use facts from the retrieved chunks; if no chunk supports a
claim, it must say so and route to needs_review.

Deterministic policy gates (SoD, recent revoke, training currency,
contractor flag) are evaluated in code so we don't depend on the LLM
reading those rules correctly.
"""

from __future__ import annotations

from typing import Any

from agents._llm import call_json
from agents.state import GraphState, TraceStep
from config import settings
from integrations import active_directory as ad
from integrations.audit_log import log_event
from rag.retriever import retrieve, format_for_prompt, RetrievedChunk


_SYSTEM = """You are the Knowledge Agent in an IT access provisioning system.

You make a recommendation for a single access request. You may ONLY use
facts that appear in the policy excerpts provided below. If the excerpts
do not directly answer a question, say so and recommend "needs_review".

Output JSON only:

{
  "decision": "auto_approve" | "needs_review" | "deny",
  "risk_tier": "low" | "medium" | "high" | "restricted" | "unknown",
  "rationale": "<2-4 sentences. Cite section names like (access_policies.md § Auto-approval).>",
  "citations": ["<source>.md § <section>", ...],
  "open_questions": ["<things you couldn't determine from the excerpts>"]
}

Guidance:
- An auto_approve recommendation is only allowed when the request is for a
  Low risk tier resource AND the retrieved excerpts clearly cover that case.
- If a deterministic block is described in the policy (e.g. SoD, recent
  for-cause revocation, contractor + employees-only), recommend "deny".
- Otherwise (Medium/High/Restricted, ambiguous, missing justification on
  PII-tagged group, etc.), recommend "needs_review".
- Never invent group names, owners, or rule numbers.
"""


def _hard_gates(state: GraphState) -> tuple[str, str] | None:
    """Run deterministic checks that don't depend on the LLM.

    Returns (decision, rationale) if a gate fires, else None.
    """
    intake = state.get("intake") or {}
    email = intake.get("requester_email") or ""
    target = intake.get("target_resource") or ""
    if not target:
        return ("needs_review",
                "Could not identify a specific group or folder from the request.")

    try:
        group = ad.get_group(target)
    except ad.ADError:
        return ("needs_review",
                f"Resource '{target}' is not in the AD group catalog. Sending to a human "
                f"to clarify or create the group.")

    if not email:
        return ("needs_review",
                "No requester identity on the message. A human must verify "
                "who is asking before granting access.")

    try:
        user = ad.get_user(email)
    except ad.ADError:
        return ("needs_review",
                f"User {email} not found in HRIS. Cannot evaluate eligibility.")

    # Contractor + employees-only → escalate to compliance (not auto-deny: per runbook)
    if user.get("employee_type") == "contractor" and "employees-only" in (group.get("tags") or []):
        return ("deny",
                f"{email} is a contractor; group '{target}' is tagged employees-only. "
                f"Per compliance_rules.md § PII-2, contractors may not be granted these "
                f"groups even with manager approval.")

    # SoD violation
    violates, conflicts = ad.would_create_sod_violation(email, target)
    if violates:
        return ("deny",
                f"Granting '{target}' would create a separation-of-duties violation with "
                f"existing membership in {', '.join(conflicts)} "
                f"(access_policies.md § Separation of duties).")

    # Recent for-cause revoke
    if ad.is_recently_revoked(email, target):
        return ("needs_review",
                f"{email} had access to '{target}' revoked for cause in the last 30 days. "
                f"Compliance Officer must review (compliance_rules.md § INT-1).")

    # Missing security training
    if not user.get("training_current", False):
        return ("deny",
                f"{email} has not completed security awareness training within the last 12 months "
                f"(access_policies.md § Eligibility rules). Direct user to LMS.")

    return None


def _build_query(state: GraphState) -> str:
    intake = state.get("intake") or {}
    parts = [
        intake.get("requested_action", ""),
        intake.get("target_resource", ""),
        intake.get("justification", ""),
        state.get("user_message", ""),
    ]
    return " | ".join(p for p in parts if p)


def run(state: GraphState) -> GraphState:
    intake = state.get("intake") or {}
    target = intake.get("target_resource") or ""

    # 1. Retrieval — always run so we have citations on the record
    try:
        chunks: list[RetrievedChunk] = retrieve(_build_query(state))
    except Exception as exc:
        log_event("knowledge_error", {"phase": "retrieve", "error": str(exc)})
        chunks = []

    # 2. Hard gates first — they're cheap and definitive
    gate = _hard_gates(state)
    if gate is not None:
        decision, rationale = gate
        # Try to surface the relevant risk tier from the catalog
        risk = "unknown"
        try:
            risk = ad.get_group(target).get("risk_tier", "unknown")
        except ad.ADError:
            pass
        citations = sorted({f"{c.source} § {c.section}" for c in chunks[:3]})
        log_event("knowledge", {
            "phase": "hard_gate",
            "decision": decision,
            "rationale": rationale,
            "risk_tier": risk,
            "citations": citations,
        })
        return {
            "retrieved_chunks": [c.to_dict() for c in chunks],
            "decision": decision,
            "decision_rationale": rationale,
            "citations": citations,
            "risk_tier": risk,
            "trace": [TraceStep(
                agent="Knowledge",
                summary=f"hard gate → {decision}",
                detail={"rationale": rationale, "citations": citations},
            )],
        }

    # 3. LLM-grounded recommendation when no hard gate fires
    user_prompt = (
        f"REQUEST CONTEXT\n"
        f"requester: {intake.get('requester_email')} ({intake.get('requester_name','')})\n"
        f"action: {intake.get('requested_action')}\n"
        f"target: {target}\n"
        f"justification: {intake.get('justification') or '(none provided)'}\n"
        f"urgency: {intake.get('urgency')}\n\n"
        f"POLICY EXCERPTS (cite by section):\n{format_for_prompt(chunks)}\n"
    )

    try:
        raw: dict[str, Any] = call_json(_SYSTEM, user_prompt)
    except Exception as exc:
        log_event("knowledge_error", {"phase": "llm", "error": str(exc)})
        return {
            "retrieved_chunks": [c.to_dict() for c in chunks],
            "decision": "needs_review",
            "decision_rationale": f"Knowledge agent LLM call failed ({exc}); routing to a human.",
            "citations": [],
            "risk_tier": "unknown",
            "trace": [TraceStep(agent="Knowledge", summary=f"llm error → needs_review")],
            "error": f"Knowledge LLM error: {exc}",
        }

    decision = raw.get("decision") or "needs_review"
    if decision not in {"auto_approve", "needs_review", "deny"}:
        decision = "needs_review"

    # Honor the global config: never auto_approve if the toggle is off
    if decision == "auto_approve" and not settings.auto_approve_low_risk:
        decision = "needs_review"

    # Auto-approve only really makes sense for Low — be defensive
    risk_tier = (raw.get("risk_tier") or "unknown").lower()
    if decision == "auto_approve" and risk_tier != "low":
        decision = "needs_review"

    rationale = raw.get("rationale") or ""
    citations = list(raw.get("citations") or [])
    if not citations and chunks:
        citations = sorted({f"{c.source} § {c.section}" for c in chunks[:3]})

    log_event("knowledge", {
        "phase": "llm",
        "decision": decision,
        "risk_tier": risk_tier,
        "rationale": rationale,
        "citations": citations,
    })

    return {
        "retrieved_chunks": [c.to_dict() for c in chunks],
        "decision": decision,  # type: ignore[typeddict-item]
        "decision_rationale": rationale,
        "citations": citations,
        "risk_tier": risk_tier,  # type: ignore[typeddict-item]
        "trace": [TraceStep(
            agent="Knowledge",
            summary=f"LLM → {decision} ({risk_tier})",
            detail={"rationale": rationale, "citations": citations},
        )],
    }
