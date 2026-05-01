# Folder & Group Access Policies

**Document owner:** IT Identity & Access Management
**Last reviewed:** 2026-03-15

## 1. Risk tiers

Every shared folder and AD group is classified into a risk tier. The risk
tier determines who can approve access and how long approval is valid.

| Tier         | Examples                                          | Approval required                              |
|--------------|---------------------------------------------------|------------------------------------------------|
| Low          | `Marketing-Public`, `Company-All-Hands`           | Auto-approved if requester is an active employee |
| Medium       | `Engineering-Source`, `Sales-Pipeline`            | Direct manager approval                         |
| High         | `Finance-Reports`, `Legal-Contracts`              | Manager + Data Owner approval                   |
| Restricted   | `Payroll-PII`, `Patient-Records`                  | Compliance Officer approval; quarterly review   |

## 2. Eligibility rules

A user MAY be granted access only if **all** of the following hold:

1. The user has an active employment record in the HRIS.
2. The user has completed the security awareness training within the last 12 months.
3. For Medium and above, the user's department is on the group's allowed
   department list, OR a documented business justification exists.
4. The user is not flagged with an active HR investigation.

A user MUST be denied access if any of the following hold:

- The user is a contractor and the group is tagged `employees-only`.
- The folder contains regulated data and the user has no
  business-need-to-know documented.
- The user has had access to the same group revoked in the last 30 days
  for cause (in which case the request must be escalated to the
  Compliance Officer regardless of justification).

## 3. Auto-approval

The Workflow Agent MAY auto-approve a request without human review if:
- The folder/group is tier **Low**, AND
- The requester is an active full-time employee, AND
- The requester has no open HR or security flags.

In all other cases the request must go through Escalation.

## 4. Time-bound access

Access is granted for a default of **90 days** for Medium tier, **30 days**
for High tier, and **7 days** for Restricted tier. The system must create
a follow-up review task before the expiry date.

## 5. Separation of duties

A single user may not simultaneously hold:
- `Finance-Reports` AND `Finance-Approvers`  (SoX violation)
- `AD-Admins` AND `Audit-Read`               (audit independence)
- `Payroll-PII` AND `Payroll-Approvers`      (SoX violation)

If a request would create one of these combinations, deny and escalate.
