# Architecture

## Use case

A working employee asks "I need access to X" in a chat. Today this hits a
human IT analyst who: (a) figures out which group the user actually means,
(b) checks the policy, (c) checks separation-of-duties / training /
contractor flags in spreadsheets, (d) either grants the access or files a
ticket to whomever can. The cycle time is hours-to-days for what is
usually a deterministic decision.

This system replaces the deterministic decisions and shortens the cycle on
the rest, while *increasing* auditability — every decision now has a log
entry, retrieved policy chunks, and a Jira ticket.

## Success metrics (measurable)

See `METRICS.md` for the full table. Headlines:

- **Auto-resolution rate** for low-risk requests: target ≥ 70%.
- **Median time-to-decision** end-to-end: target < 60 seconds.
- **Wrong-decision rate** measured by audit replay: target < 1%.
- **CSAT** on the user-facing reply: ≥ 4 / 5.

## Agent contract

Each agent exposes a single function `run(state: GraphState) -> GraphState`
that returns a *partial* state delta. LangGraph merges deltas into the
running state. Agents never reach into each other's modules.

### Intake Agent
- **Input:** raw message, requester identity hint.
- **Output:** structured `IntakeFields` (action, target, justification,
  urgency, confidence).
- **Constraints:** does not decide, does not retrieve, does not act.

### Knowledge Agent
- **Input:** structured intake.
- **Output:** decision ∈ {auto_approve, needs_review, deny}, risk tier,
  rationale, citations.
- **Process:**
  1. Run hard gates in code (SoD, recent revoke, contractor + employees-only,
     training currency, unknown user/group).
  2. If no gate fires, retrieve top-k policy chunks via Chroma.
  3. Ask the LLM for a JSON decision *grounded only in the chunks*.
  4. Defensively cap auto_approve to risk_tier=low.

### Workflow Agent
- Runs only on `auto_approve`.
- Idempotently adds the user to the AD group via the integrations adapter.
- Files an informational Jira ticket so humans see auto-grants in their
  queue.
- Drafts the user-facing reply.

### Escalation Agent
- Runs on `needs_review` or `deny`.
- Picks the assignee using the routing matrix in `escalation_runbook.md`
  (compliance for SoD/revoke/restricted, data owner for high, manager for
  medium, helpdesk fallback).
- Picks priority from urgency (P3 default; P2 on "blocked"; P1 on "urgent").
- Files the Jira ticket and writes the user-facing reply via the LLM,
  with a deterministic fallback string if the LLM call fails.

## Why hard gates AND the LLM

The four obvious failure modes for an LLM-only system are:
1. The LLM hallucinates a policy that doesn't exist.
2. The LLM misses a SoD violation because the conflict is implicit.
3. The LLM auto-approves something restricted because the user pleads.
4. The LLM is unavailable.

Hard gates handle 2, 3, and 4. RAG citations make 1 detectable in audit.

## RAG details

- **Chunking:** header-aware (splits on `## ` / `### `). Each policy
  section is one chunk, so citations align with the section name a human
  would read in the source markdown.
- **Embeddings:** `text-embedding-3-small`. Switch to large for
  production-grade recall.
- **Vector DB:** ChromaDB persistent client. Drop-in replacement for
  Pinecone/Weaviate later — the retriever interface returns
  `RetrievedChunk(text, source, section, score)`.
- **Top-k:** 4 by default. Tune in `config.py`.

## Integration boundaries

| Module                            | Real-world equivalent                      |
|-----------------------------------|--------------------------------------------|
| `integrations/active_directory.py`| MS Graph / `ldap3` / Okta SCIM             |
| `integrations/jira_client.py`     | Jira REST or MCP server                    |
| `integrations/audit_log.py`       | Splunk / Datadog audit pipeline            |
| `rag/`                            | Glean / enterprise RAG                     |

The agent layer never imports anything external — only these modules. To
go real, replace the file bodies and keep the function signatures.

## MCP positioning

This prototype uses LangGraph because it gives us explicit, inspectable
state transitions. In an MCP-first deployment you would expose the same
tools (`grant_access`, `lookup_user`, `create_ticket`, `retrieve_policy`)
as MCP tools and have a Claude or other model client orchestrate them.
The agent code in this repo would shrink — it would mostly be the
orchestration logic and the prompts. The hard gates and RAG layer would
move into the MCP server.

## Scaling

- **Throughput:** the graph is stateless per request; horizontally scale
  by running N workers behind a queue. Chroma can be moved to its server
  mode or swapped for Pinecone with no agent changes.
- **Catalog growth:** the AD catalog and policy KB are independent. Adding
  a new group is a JSON edit; adding new policy is a markdown commit and
  a re-run of `python -m rag.ingest`.
- **New compliance regime:** add a hard gate (small code change in
  `agents/knowledge._hard_gates`) and a policy markdown chunk. No graph
  topology changes.
