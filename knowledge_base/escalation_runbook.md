# Escalation Runbook

Not every access request can be (or should be) auto-resolved. This runbook
defines who an unresolved request goes to and how the Escalation Agent
must format the handoff.

## Routing matrix

| Trigger                                              | Route to               | SLA (business hours) |
|------------------------------------------------------|------------------------|----------------------|
| Medium-tier group, no obvious blocker                | Direct manager         | 4h                   |
| High-tier group                                      | Manager + Data Owner   | 8h                   |
| Restricted-tier group                                | Compliance Officer     | 24h                  |
| Contractor requesting `employees-only`               | Compliance Officer     | 24h                  |
| SoD (separation-of-duties) violation                 | Compliance Officer     | Same day             |
| Recent revocation (<30 days)                         | Compliance Officer     | Same day             |
| Missing required training                            | Auto-deny, point to LMS| n/a                  |
| Ambiguous request (cannot identify folder/user)      | IT helpdesk            | 4h                   |
| User says they're locked out / blocked / urgent      | IT helpdesk (priority) | 1h                   |

## Ticket format

The Escalation Agent creates Jira tickets with this structure:

- **Summary:** `[Access Request] {requester_name} → {resource} ({risk_tier})`
- **Description:**
  - Verbatim user request
  - Structured fields extracted by the Intake Agent
  - Knowledge Agent recommendation and the policy citations behind it
  - The current step the workflow stopped at, and why
- **Labels:** `access-request`, `auto-routed`, plus the risk tier
- **Priority:** P3 default, P2 if "blocked" or "deadline" appears in
  the request, P1 if outage language is detected.
- **Assignee:** populated from the routing matrix above.

## Communication to the user

Every escalation must produce a user-facing reply that:
1. Acknowledges the request was received and parsed.
2. States *exactly why* the system did not auto-fulfill (with policy citation).
3. Names the human who now owns the ticket.
4. Gives the ticket ID and the SLA.
5. Tells the user what they should or shouldn't do next.

Avoid hedging language ("the system thinks", "probably") — be specific.
