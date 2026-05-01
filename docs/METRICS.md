# Success Metrics

How we know the system is working — and worth keeping.

## Core metrics

| Metric                       | How it's measured                                | Target    |
|------------------------------|--------------------------------------------------|-----------|
| Auto-resolution rate         | % of requests where Workflow Agent ran           | ≥ 70% for low-risk; ≥ 30% overall |
| Median time-to-decision      | request_received → request_completed (audit log) | < 60s     |
| Time-to-grant (auto)         | Same, restricted to auto_approve                 | < 30s     |
| Wrong-decision rate          | Compliance audit replay sample (50/quarter)      | < 1%      |
| Escalation accuracy          | % of escalations that the picked assignee accepts as theirs | ≥ 95% |
| User satisfaction (CSAT)     | 1–5 thumbs survey on the assistant reply         | ≥ 4.0     |
| Self-service deflection      | Tickets handled without analyst touch            | ≥ 50% |
| Hallucination flag rate      | Reviewer flags ≥ 1 unsupported claim in rationale | < 2%     |

## Operational metrics (catch regressions early)

| Metric                          | Source                              | Alert if          |
|---------------------------------|-------------------------------------|-------------------|
| LLM error rate                  | `audit_log.jsonl` `*_error` events  | > 1% over 1h      |
| Retrieval empty rate            | `knowledge` events with no chunks   | > 0.5% over 1h    |
| Hard-gate fire rate by type     | `knowledge` events `phase=hard_gate`| Sudden 3× change  |
| AD write failure                | `workflow_error`                    | Any in 5 min      |
| Average top-1 retrieval score   | Computed over last 1k requests      | < 0.7             |

## Qualitative checks

- **Audit replay drill** — every quarter, a compliance reviewer picks 30
  random requests from the audit log and re-renders the decision. They
  flag any decision they disagree with. This is the canonical "wrong-
  decision rate" measurement.
- **Red-team prompts** — a fixed pack of prompts that try to trick the
  LLM into auto-approving restricted resources. Run on every model
  upgrade. Failures block release.

## Why these and not others

We deliberately avoided "tickets per analyst per day" — it's a vanity
metric that goes up if you make decisions worse. Auto-resolution rate
combined with wrong-decision rate keeps the system honest: you can't
look good on one without paying on the other.
