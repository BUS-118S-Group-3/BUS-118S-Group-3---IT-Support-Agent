"""Shared pytest fixtures.

The tests run completely offline: no real OpenAI calls and no real
ChromaDB. We monkey-patch:
  - rag.retriever.retrieve     → returns a small canned set of chunks
  - agents._llm.call_json      → returns whatever the test sets up
  - agents._llm.call_text      → returns a deterministic string
  - integrations.audit_log + jira state directories → tmp dirs

This lets us exercise the full LangGraph wiring while pinning the
behaviour of the LLM/RAG layer.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

# Make the project importable when pytest is run from project root.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path, monkeypatch):
    """Redirect data/ + audit log + chroma store into a temp dir per test."""
    src_data = ROOT / "data"
    dst_data = tmp_path / "data"
    dst_data.mkdir()
    for name in ("users.json", "groups.json"):
        shutil.copy(src_data / name, dst_data / name)

    from config import settings as real
    monkeypatch.setattr(real, "data_dir", dst_data, raising=False)
    monkeypatch.setattr(real, "audit_log_path", dst_data / "audit_log.jsonl", raising=False)
    monkeypatch.setattr(real, "chroma_dir", tmp_path / "chroma_store", raising=False)

    # Re-point the AD/jira store paths used at module import time
    from integrations import active_directory as ad_mod
    from integrations import jira_client as jira_mod
    monkeypatch.setattr(ad_mod, "_users", ad_mod._JsonStore(dst_data / "users.json"))
    monkeypatch.setattr(ad_mod, "_groups", ad_mod._JsonStore(dst_data / "groups.json"))
    monkeypatch.setattr(jira_mod, "_TICKETS_PATH", dst_data / "tickets.json")
    yield


@pytest.fixture
def stub_rag(monkeypatch):
    """Replace rag.retriever.retrieve with a callable that returns canned chunks."""
    from rag.retriever import RetrievedChunk

    canned: list[RetrievedChunk] = [
        RetrievedChunk(
            text="Auto-approval applies to Low tier groups for active full-time employees.",
            source="access_policies.md",
            section="Auto-approval",
            score=0.92,
        ),
        RetrievedChunk(
            text="Members of Finance-Approvers may not also hold Finance-Reports.",
            source="access_policies.md",
            section="Separation of duties",
            score=0.88,
        ),
    ]

    def _fake_retrieve(query, k=None):
        return list(canned)

    import rag.retriever as r
    import agents.knowledge as k
    monkeypatch.setattr(r, "retrieve", _fake_retrieve)
    monkeypatch.setattr(k, "retrieve", _fake_retrieve)


@pytest.fixture
def stub_llm(monkeypatch):
    """Pin LLM responses so tests are deterministic."""
    from agents import _llm

    state = {
        "intake": None,            # set by test
        "knowledge": None,         # set by test
        "text": "STUB user-facing reply.",
    }

    def _call_json(system, user, **kwargs):
        if "Intake Agent" in system:
            return state["intake"]
        if "Knowledge Agent" in system:
            return state["knowledge"]
        raise RuntimeError(f"Unexpected system prompt: {system[:40]}")

    def _call_text(system, user, **kwargs):
        return state["text"]

    monkeypatch.setattr(_llm, "call_json", _call_json)
    monkeypatch.setattr(_llm, "call_text", _call_text)
    # The agents bind these at import-time, so patch the module-level names too
    import agents.intake as intake_mod
    import agents.knowledge as knowledge_mod
    import agents.escalation as escalation_mod
    monkeypatch.setattr(intake_mod, "call_json", _call_json)
    monkeypatch.setattr(knowledge_mod, "call_json", _call_json)
    monkeypatch.setattr(escalation_mod, "call_text", _call_text)

    return state


@pytest.fixture
def fresh_graph(monkeypatch):
    """Drop the cached compiled graph between tests."""
    from agents import orchestrator
    orchestrator.build_graph.cache_clear()
    yield
    orchestrator.build_graph.cache_clear()
