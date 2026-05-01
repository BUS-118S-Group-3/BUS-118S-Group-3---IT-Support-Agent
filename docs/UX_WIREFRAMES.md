# UX Wireframes

The interface mirrors the way employees already submit IT requests: a
chat. Visual mockups below are ASCII so they live next to the code; the
Streamlit `app.py` is the running implementation.

## Design principles

1. **One thing on screen.** A user with a problem doesn't want a form
   with twelve fields. They want to type what they need. The chat is
   the only required surface; everything else is optional reveal.
2. **Show your work.** Every reply states the decision, the policy
   citations, and the ticket number. Hidden behaviour is what makes
   internal tools feel hostile.
3. **No hedging in the user reply.** "The system thinks" / "probably"
   is replaced with concrete language: "Granted." / "Denied because…" /
   "Routed to Carmen Diaz, ticket ITACCESS-23, response within 4h."
4. **Reversibility is visible.** Auto-grants show their expiry. Denied
   requests tell the user what would change the answer (drop the
   conflicting group, complete training, get manager sign-off).

## Main screen — initial state

```
 ┌────────────────────────────────────────────────────────────────────────┐
 │  🔒 Automated Access Provisioning                                      │
 │  Multi-agent IT support: Intake → Knowledge → Workflow / Escalation    │
 ├──────────────┬─────────────────────────────────────────────────────────┤
 │  Sign in as  │                                                         │
 │  [Alice ▼]   │                                                         │
 │  full-time   │                                                         │
 │  Marketing   │                                                         │
 │              │       (chat is empty — only the input bar shows)        │
 │  Try a       │                                                         │
 │  scenario    │                                                         │
 │  ────────    │                                                         │
 │  • Auto      │                                                         │
 │  • Manager   │                                                         │
 │  • Restrict  │                                                         │
 │  • SoD deny  │                                                         │
 │  • Contract  │                                                         │
 │  • Revoked   │                                                         │
 │  • Urgent    │                                                         │
 │  • Ambiguous │                                                         │
 │              ├─────────────────────────────────────────────────────────┤
 │  Recent      │  ▢ Describe what you need access to…                    │
 │  tickets     │                                                         │
 │  ITA-12 P3   │                                                         │
 │  ITA-11 P2   │                                                         │
 └──────────────┴─────────────────────────────────────────────────────────┘
```

## After an auto-approve

```
 ┌──────────────────────────────────────────────────────────────────────┐
 │  user                                                                │
 │  ─ Hi, I'm starting a campaign and need access to Marketing-Public.  │
 │                                                                      │
 │  assistant                                                           │
 │   [auto_approve]  4.1s                                               │
 │                                                                      │
 │   Done — alice.nguyen@acme.example has been added to                 │
 │   **Marketing-Public**.                                              │
 │   • Risk tier: low                                                   │
 │   • Audit ticket: ITACCESS-13                                        │
 │   • Policy basis: access_policies.md § Auto-approval                 │
 │                                                                      │
 │  ┌─ Agent trace ────────────┐  ┌─ Structured intake ─────────────┐   │
 │  │ ▸ Intake — extracted…    │  │ requester_email: alice.nguyen…  │   │
 │  │ ▸ Knowledge — LLM → low  │  │ target_resource: Marketing-…    │   │
 │  │ ▸ Workflow — granted     │  │ urgency: normal                 │   │
 │  └──────────────────────────┘  └─────────────────────────────────┘   │
 │  ┌─ Retrieved policy chunks ────────────────────────────────────┐    │
 │  │ ▸ access_policies.md § Auto-approval     score 0.92          │    │
 │  │ ▸ access_policies.md § Risk tiers        score 0.87          │    │
 │  └──────────────────────────────────────────────────────────────┘    │
 └──────────────────────────────────────────────────────────────────────┘
```

The colored pill (auto_approve / needs_review / deny) is the most
important visual element on the page — it is what a user sees first.

## After a denial (SoD violation)

```
 ┌──────────────────────────────────────────────────────────────────────┐
 │  assistant                                                           │
 │   [deny]  3.0s                                                       │
 │                                                                      │
 │   Your request to be added to Finance-Reports has been denied.       │
 │   You currently hold Finance-Approvers, and access_policies.md       │
 │   § Separation of duties forbids holding both                        │
 │   (SoX-1).                                                           │
 │                                                                      │
 │   Tracking ticket: ITACCESS-14 (compliance@acme.example, SLA 24h).   │
 │                                                                      │
 │   To proceed: ask Compliance to remove you from Finance-Approvers    │
 │   first, then re-submit.                                             │
 └──────────────────────────────────────────────────────────────────────┘
```

Note the structure: what happened, why (with a citation), who owns the
record, and what the user can do about it.

## After an escalation

```
 ┌──────────────────────────────────────────────────────────────────────┐
 │  assistant                                                           │
 │   [needs_review]  3.6s                                               │
 │                                                                      │
 │   Got it — your request for Sales-Pipeline has been routed to your   │
 │   manager Carmen Diaz for approval, ticket ITACCESS-15 (SLA 4h).     │
 │   Reason: Sales-Pipeline is a Medium-tier resource and per           │
 │   access_policies.md § Risk tiers it requires direct manager         │
 │   approval. You don't need to do anything else; Carmen will reach    │
 │   out if she needs more context.                                     │
 └──────────────────────────────────────────────────────────────────────┘
```

## Sidebar — example prompts

The example prompts are deliberately phrased the way an employee would
ask, not the way a form would frame it. This is the single most
important thing about the UX: you are talking to the system, not
filling in a request type.

## Mobile / inline considerations

This UI also runs inline in any chat surface (Slack, Teams) using the
same orchestrator. The trace and audit panels become a "show details"
expansion the user can request explicitly with `/access trace`.

## Accessibility checklist

- All decisions are encoded in text, not just color (`auto_approve` etc.).
- Pill colors meet WCAG AA contrast.
- The chat respects keyboard-only navigation.
- The trace panels collapse by default — they are progressive disclosure,
  not the primary content.
