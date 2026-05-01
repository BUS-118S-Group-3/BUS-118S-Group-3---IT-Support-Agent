# Compliance Rules

This document maps regulatory regimes to the access-decision rules the
agents must enforce. Citations are deliberately concrete so the Knowledge
Agent can quote them in user-facing explanations.

## SoX (Sarbanes-Oxley)

Applies to any access touching financial reporting workflows.

- **Rule SoX-1 — Separation of duties.** No single user may both prepare
  and approve a financial transaction. The combinations
  `Finance-Reports + Finance-Approvers` and
  `Payroll-PII + Payroll-Approvers` are forbidden.
- **Rule SoX-2 — Quarterly attestation.** Membership in `Finance-Approvers`,
  `Payroll-Approvers`, and `AD-Admins` must be re-attested by the CFO or
  CISO every 90 days. The system creates an attestation task at grant time.
- **Rule SoX-3 — Audit independence.** Members of `Audit-Read` must not
  also hold `AD-Admins`.

## PII / GDPR / CCPA

- **Rule PII-1 — Business need-to-know.** Access to any folder tagged
  `pii` requires a documented business justification stored on the ticket.
  Requests with no justification, or with a justification that does not
  reference a specific business activity, must be denied.
- **Rule PII-2 — Contractor restriction.** Contractors may not be granted
  access to groups tagged `employees-only` even with manager approval.
  Such requests must be escalated to the Compliance Officer.
- **Rule PII-3 — Time-bound.** PII access is time-bound (max 90 days,
  default 30 for restricted tier).

## HIPAA (where applicable)

- **Rule HIPAA-1 — Minimum necessary.** When the request mentions a
  research or clinical workflow, access must be scoped to the smallest
  set of records that support the stated purpose. The Knowledge Agent
  should suggest narrower-scope groups when available.
- **Rule HIPAA-2 — Training.** HIPAA training currency (within 12 months)
  must be confirmed before granting any access to `Patient-Records` or
  derived datasets.

## Internal — Recently revoked

- **Rule INT-1.** If a user had access to the same group revoked within
  the last 30 days for cause, the request must be escalated to the
  Compliance Officer regardless of business justification.

## Internal — High-risk roles

- **Rule INT-2.** Members of `AD-Admins`, `Finance-Approvers`, and
  `Payroll-Approvers` must use phishing-resistant MFA. The Workflow
  Agent must not grant these without confirming MFA enrollment.
