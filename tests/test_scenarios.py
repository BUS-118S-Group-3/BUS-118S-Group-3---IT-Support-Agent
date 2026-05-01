"""End-to-end scenario tests.

The LLM and the vector store are stubbed (see conftest). These tests
verify the wiring: the right hard-gate fires, the right node runs, the
right side-effect is recorded.
"""

from __future__ import annotations

import pytest


def _intake(target: str, action: str = "grant", justification: str = "", urgency: str = "normal"):
    return {
        "requester_email": "",   # filled in by orchestrator from hint
        "requested_action": action,
        "target_resource": target,
        "justification": justification,
        "urgency": urgency,
        "confidence": 0.9,
        "notes": "",
    }


def _llm_decision(decision: str, risk: str, rationale: str, citations=None):
    return {
        "decision": decision,
        "risk_tier": risk,
        "rationale": rationale,
        "citations": citations or ["access_policies.md § Auto-approval"],
        "open_questions": [],
    }


def test_low_risk_auto_approve(stub_rag, stub_llm, fresh_graph):
    """Marketing-Public for an active employee should auto-approve and modify AD."""
    stub_llm["intake"] = _intake("Marketing-Public", justification="campaign launch")
    stub_llm["knowledge"] = _llm_decision("auto_approve", "low",
                                          "Low-tier resource for active employee.")
    from agents.orchestrator import run
    from integrations import active_directory as ad

    state = run("I need Marketing-Public for a campaign.",
                requester_email="bob.singh@acme.example")

    assert state["decision"] == "auto_approve"
    assert state["ad_changed"] is True
    assert "bob.singh@acme.example" in ad.get_group("Marketing-Public")["members"]
    assert state["ticket_key"]


def test_medium_routes_to_escalation(stub_rag, stub_llm, fresh_graph):
    stub_llm["intake"] = _intake("Sales-Pipeline", justification="Q3 review")
    stub_llm["knowledge"] = _llm_decision("needs_review", "medium",
                                          "Medium tier requires manager approval.")
    from agents.orchestrator import run
    from integrations import active_directory as ad

    state = run("Add me to Sales-Pipeline.",
                requester_email="alice.nguyen@acme.example")

    assert state["decision"] == "needs_review"
    assert state["ad_changed"] is False
    assert "alice.nguyen@acme.example" not in ad.get_group("Sales-Pipeline")["members"]
    assert state["ticket_key"]


def test_sod_violation_denied_by_hard_gate(stub_rag, stub_llm, fresh_graph):
    """Fiona is in Finance-Approvers; asking for Finance-Reports must deny in code."""
    stub_llm["intake"] = _intake("Finance-Reports", justification="board pack")
    # Hard gate should run before the LLM, but provide a knowledge response anyway:
    stub_llm["knowledge"] = _llm_decision("auto_approve", "high", "would be wrong")
    from agents.orchestrator import run
    from integrations import active_directory as ad

    state = run("Add me to Finance-Reports.",
                requester_email="fiona.reed@acme.example")

    assert state["decision"] == "deny"
    assert state["ad_changed"] is False
    # AD must not have been modified
    assert "fiona.reed@acme.example" not in ad.get_group("Finance-Reports")["members"]
    # Should be routed to compliance per runbook
    assert state["ticket_key"]


def test_contractor_employees_only_denied(stub_rag, stub_llm, fresh_graph):
    stub_llm["intake"] = _intake("Legal-Contracts", justification="SOW review")
    stub_llm["knowledge"] = _llm_decision("auto_approve", "high", "would be wrong")
    from agents.orchestrator import run

    state = run("Add me to Legal-Contracts.",
                requester_email="evan.park@acme.example")
    assert state["decision"] == "deny"
    assert "contractor" in (state.get("decision_rationale") or "").lower()


def test_recent_revoke_routes_to_compliance(stub_rag, stub_llm, fresh_graph):
    stub_llm["intake"] = _intake("Engineering-Secrets", justification="deploy")
    stub_llm["knowledge"] = _llm_decision("auto_approve", "high", "would be wrong")
    from agents.orchestrator import run

    state = run("Add me back to Engineering-Secrets.",
                requester_email="hana.kim@acme.example")
    assert state["decision"] == "needs_review"
    assert state["ticket_key"]


def test_missing_training_denied(stub_rag, stub_llm, fresh_graph):
    stub_llm["intake"] = _intake("Sales-Pipeline", justification="forecast review")
    stub_llm["knowledge"] = _llm_decision("auto_approve", "medium", "would be wrong")
    from agents.orchestrator import run

    state = run("Add me to Sales-Pipeline.",
                requester_email="gus.olsen@acme.example")
    assert state["decision"] == "deny"
    assert "training" in (state.get("decision_rationale") or "").lower()


def test_unknown_resource_routes_to_review(stub_rag, stub_llm, fresh_graph):
    stub_llm["intake"] = _intake("Made-Up-Group")
    stub_llm["knowledge"] = _llm_decision("auto_approve", "low", "would be wrong")
    from agents.orchestrator import run

    state = run("Add me to Made-Up-Group.",
                requester_email="alice.nguyen@acme.example")
    assert state["decision"] == "needs_review"
    assert state["ticket_key"]


def test_audit_log_records_each_decision(stub_rag, stub_llm, fresh_graph):
    from integrations.audit_log import read_recent

    stub_llm["intake"] = _intake("Marketing-Public", justification="press kit")
    stub_llm["knowledge"] = _llm_decision("auto_approve", "low", "Low tier auto.")
    from agents.orchestrator import run
    run("Marketing-Public please.", requester_email="alice.nguyen@acme.example")

    types = [e["type"] for e in read_recent(limit=20)]
    assert "request_received" in types
    assert "intake" in types
    assert "knowledge" in types
    assert "workflow_grant" in types
    assert "request_completed" in types


def test_route_priority_escalates_on_blocked_urgency(stub_rag, stub_llm, fresh_graph):
    stub_llm["intake"] = _intake("Sales-Pipeline", justification="Q3", urgency="blocked")
    stub_llm["knowledge"] = _llm_decision("needs_review", "medium", "Manager approval.")
    from agents.orchestrator import run
    from integrations import jira_client as jira

    state = run("Sales-Pipeline now please, blocked.",
                requester_email="alice.nguyen@acme.example")
    assert state["decision"] == "needs_review"
    ticket = jira.get_ticket(state["ticket_key"])
    assert ticket["fields"]["priority"]["name"] == "P2"
