# AD Group / Folder Catalog

This is the canonical catalog of shared folders and AD groups, their owners,
and their classification. The Knowledge Agent uses it to look up the risk
tier of a requested resource.

## Marketing & Communications

### Marketing-Public
- **Risk tier:** Low
- **Path:** `\\fs01\shared\marketing\public`
- **Data owner:** marketing.ops@acme.example
- **Allowed departments:** all employees
- **Description:** Brand assets, public press kits, externally shareable decks.

### Marketing-Campaigns
- **Risk tier:** Medium
- **Path:** `\\fs01\shared\marketing\campaigns`
- **Data owner:** cmo@acme.example
- **Allowed departments:** Marketing, Sales, Product
- **Description:** In-flight campaign drafts, launch plans, embargoed materials.

## Engineering

### Engineering-Source
- **Risk tier:** Medium
- **Path:** `\\fs01\shared\engineering\source` (mirror of git for legacy access)
- **Data owner:** vp.engineering@acme.example
- **Allowed departments:** Engineering, Security
- **Description:** Source code mirror, build artifacts.

### Engineering-Secrets
- **Risk tier:** High
- **Path:** `\\fs01\shared\engineering\secrets`
- **Data owner:** ciso@acme.example
- **Allowed departments:** Security, Platform
- **Tags:** `employees-only`
- **Description:** Production credentials staging area. Highly restricted.

## Finance & Legal

### Finance-Reports
- **Risk tier:** High
- **Path:** `\\fs01\shared\finance\reports`
- **Data owner:** cfo@acme.example
- **Allowed departments:** Finance, Executive
- **Description:** Internal P&L, board reports, forecasts.

### Finance-Approvers
- **Risk tier:** Restricted
- **Path:** AD group only (no folder)
- **Data owner:** cfo@acme.example
- **Description:** SoX-controlled approver group. Quarterly attestation.

### Legal-Contracts
- **Risk tier:** High
- **Path:** `\\fs01\shared\legal\contracts`
- **Data owner:** general.counsel@acme.example
- **Allowed departments:** Legal, Executive
- **Tags:** `employees-only`

## HR & Payroll

### Payroll-PII
- **Risk tier:** Restricted
- **Path:** `\\fs01\shared\hr\payroll`
- **Data owner:** chro@acme.example
- **Allowed departments:** HR-Payroll
- **Tags:** `employees-only`, `pii`, `sox`
- **Description:** SSN, bank account, salary data. Compliance Officer approval required.

### Payroll-Approvers
- **Risk tier:** Restricted
- **Description:** SoX-controlled approver group; mutually exclusive with `Payroll-PII`.

## Sales

### Sales-Pipeline
- **Risk tier:** Medium
- **Path:** `\\fs01\shared\sales\pipeline`
- **Data owner:** vp.sales@acme.example
- **Allowed departments:** Sales, Marketing, Executive

### Sales-Customer-Lists
- **Risk tier:** High
- **Tags:** `pii`
- **Allowed departments:** Sales, Customer-Success
- **Description:** Contains customer contact PII. Subject to GDPR/CCPA review.

## Compliance / Audit

### Audit-Read
- **Risk tier:** High
- **Description:** Read-only audit trail across systems. Mutually exclusive with AD-Admins.

### AD-Admins
- **Risk tier:** Restricted
- **Description:** Active Directory administrators. Quarterly attestation, MFA-only.
