# Access Provisioning FAQ

## How long do I keep access once it's granted?

It depends on the risk tier of the resource:
- Low: indefinite while you remain an active employee.
- Medium: 90 days, then a re-justification ticket is created.
- High: 30 days, with manager + data-owner re-attestation.
- Restricted: 7 days; renewals require Compliance Officer sign-off.

## I had access yesterday and now I don't. What happened?

Three common causes:
1. **Time-bound expiry.** Look at the original grant ticket — if it's
   past the SLA, the system removed you on schedule.
2. **HR change.** A department transfer can revoke department-scoped
   group memberships automatically.
3. **Policy violation revoke.** If you triggered a security flag, your
   Compliance Officer was notified before the revoke. Check email.

## I'm a contractor and need to see internal contracts. What now?

Contractors can never be granted `employees-only` groups (Rule PII-2).
Possible paths: ask your sponsoring manager to request a redacted copy,
or ask Legal to share specific documents through the contractor portal.

## My manager is on leave — can someone else approve?

Yes. The Escalation Agent will pick the manager's delegated approver
from the HRIS. If no delegate is set, the request routes one level up
in the org chart and the original manager is CC'd for visibility.

## What's the difference between "denied" and "escalated"?

- **Denied** means the request is blocked by policy and no human review
  will change that (e.g., a SoD violation). You'll receive a citation
  for the rule. To proceed you'd need to drop one of the conflicting
  memberships first.
- **Escalated** means the system can't auto-decide and needs a human
  approver. A Jira ticket is open and someone will respond within SLA.
