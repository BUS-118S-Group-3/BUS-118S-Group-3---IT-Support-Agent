"""IT admin dashboard.

Pending escalation queue with one-click approve / deny / reassign.
Full audit log. Stats. Per-ticket detail with the original Knowledge
Agent rationale and citations so the admin can decide quickly.

Cleanly separated from the user page — end users never see this.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import streamlit as st

from agents import admin_actions
from integrations import active_directory as ad
from integrations import jira_client as jira
from integrations.audit_log import read_recent

st.set_page_config(page_title="IT Admin", page_icon=":wrench:", layout="wide")

st.markdown(
    """
    <style>
      .small { font-size: 0.85rem; color: #555; }
      .pillok { background:#e6f4ea;color:#1e7c2c;padding:2px 8px;border-radius:8px; }
      .pillrv { background:#fff4ce;color:#7c5b00;padding:2px 8px;border-radius:8px; }
      .pilldn { background:#fde2e2;color:#a31515;padding:2px 8px;border-radius:8px; }
      .pillgr { background:#dbe8ff;color:#1d4ed8;padding:2px 8px;border-radius:8px; }
      .stat-card {
          padding: 16px;
          border: 1px solid #e2e2e2;
          border-radius: 8px;
          background: #fafafa;
      }
      .stat-num { font-size: 1.6rem; font-weight: 600; }
      .stat-lbl { color: #555; font-size: 0.85rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("IT Admin Dashboard")

# ---- Sidebar: identity, refresh, nav ----
with st.sidebar:
    st.subheader("Acting as")
    admin = st.text_input(
        "Your email",
        value=st.session_state.get("admin_email", "compliance@acme.example"),
        key="admin_email",
    )
    st.caption("All approvals/denials are recorded under this name.")

    st.divider()
    if st.button("↻ Refresh", use_container_width=True):
        st.rerun()
    st.caption("Streamlit auto-refreshes when you act on a ticket.")

    st.divider()
    if st.button("← Back to landing", use_container_width=True):
        st.switch_page("app.py")

# ---- Stats strip ----
s = admin_actions.stats()
c1, c2, c3, c4 = st.columns(4)
for col, num, label in [
    (c1, s["total_requests"], "Total tickets"),
    (c2, s["pending_escalations"], "Awaiting review"),
    (c3, f"{s['auto_resolution_rate']*100:.0f}%", "Auto-resolution rate"),
    (c4, s["by_decision"].get("deny", 0), "Denied (policy)"),
]:
    with col:
        st.markdown(
            f"<div class='stat-card'><div class='stat-num'>{num}</div>"
            f"<div class='stat-lbl'>{label}</div></div>",
            unsafe_allow_html=True,
        )

st.write("")
tab_queue, tab_all, tab_audit = st.tabs(
    ["Pending escalations", "All tickets", "Audit log"]
)

# =====================================================================
# Tab 1: pending escalations + approve/deny controls
# =====================================================================
with tab_queue:
    pending = admin_actions.list_pending_escalations()

    if not pending:
        st.success("No pending escalations. Inbox zero.")
    else:
        st.caption(f"{len(pending)} ticket(s) awaiting decision.")
        for t in pending:
            f = t["fields"]
            md = t.get("metadata") or {}
            decision = md.get("decision", "—")
            decision_pill = {"deny": "pilldn", "needs_review": "pillrv"}.get(
                decision, "small"
            )
            with st.expander(
                f"{t['key']} · {f['priority']['name']} · {f['summary']}",
                expanded=False,
            ):
                left, right = st.columns([2, 1])

                with left:
                    st.markdown(
                        f"<span class='{decision_pill}'>{decision}</span> "
                        f"<span class='small'>risk: {md.get('risk_tier','?')} · "
                        f"SLA: {md.get('sla','?')} · "
                        f"updated: {f.get('updated','')}</span>",
                        unsafe_allow_html=True,
                    )
                    st.write(f"**Requester:** {md.get('requester_email','?')}")
                    st.write(f"**Resource:** {md.get('target_resource','?')}")
                    st.write(
                        f"**Justification:** {md.get('justification') or '_(none provided)_'}"
                    )
                    st.write(f"**Original message:** {md.get('user_message','')!r}")
                    st.write("**Knowledge Agent rationale:**")
                    st.info(md.get("rationale") or "(no rationale recorded)")
                    cites = md.get("citations") or []
                    if cites:
                        st.caption("Policy basis: " + "; ".join(cites))

                    if f.get("comments"):
                        st.write("**Comment trail:**")
                        for c in f["comments"]:
                            st.markdown(
                                f"<span class='small'>"
                                f"`{c.get('ts','')}` · "
                                f"{c.get('actor','?')}: {c.get('note','')}"
                                f"</span>",
                                unsafe_allow_html=True,
                            )

                with right:
                    st.markdown("**Take action**")
                    note = st.text_area(
                        "Note (optional)",
                        key=f"note_{t['key']}",
                        height=80,
                    )
                    bcol1, bcol2 = st.columns(2)
                    with bcol1:
                        if st.button(
                            "Approve",
                            key=f"approve_{t['key']}",
                            use_container_width=True,
                            type="primary",
                            disabled=(decision == "deny"),
                            help="Disabled — Knowledge Agent recommended deny." if decision == "deny" else None,
                        ):
                            try:
                                res = admin_actions.approve_escalation(
                                    t["key"], admin, note
                                )
                                st.success(res.message)
                                st.rerun()
                            except admin_actions.AdminActionError as exc:
                                st.error(str(exc))
                    with bcol2:
                        if st.button(
                            "Deny",
                            key=f"deny_{t['key']}",
                            use_container_width=True,
                        ):
                            try:
                                res = admin_actions.deny_escalation(
                                    t["key"], admin, note
                                )
                                st.warning(res.message)
                                st.rerun()
                            except admin_actions.AdminActionError as exc:
                                st.error(str(exc))

                    st.write("")
                    new_assignee = st.text_input(
                        "Reassign to",
                        key=f"reassign_in_{t['key']}",
                        placeholder="email@acme.example",
                    )
                    if st.button(
                        "Reassign",
                        key=f"reassign_{t['key']}",
                        use_container_width=True,
                    ):
                        if new_assignee.strip():
                            res = admin_actions.reassign_escalation(
                                t["key"], new_assignee.strip(), admin, note
                            )
                            st.info(res.message)
                            st.rerun()
                        else:
                            st.error("Provide an email to reassign to.")

# =====================================================================
# Tab 2: all tickets table
# =====================================================================
with tab_all:
    all_t = jira.list_tickets(limit=200)
    if not all_t:
        st.caption("No tickets yet.")
    else:
        rows = []
        for t in all_t:
            f = t["fields"]
            md = t.get("metadata") or {}
            rows.append({
                "Key": t["key"],
                "Status": f["status"]["name"],
                "Priority": f["priority"]["name"],
                "Decision": md.get("decision", "—"),
                "Risk": md.get("risk_tier", "—"),
                "Requester": md.get("requester_email", "—"),
                "Resource": md.get("target_resource", "—"),
                "Assignee": f["assignee"]["emailAddress"],
                "Updated": f.get("updated", ""),
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)

# =====================================================================
# Tab 3: audit log
# =====================================================================
with tab_audit:
    limit = st.slider("Show last N events", min_value=10, max_value=200, value=50, step=10)
    events = read_recent(limit=limit)
    if not events:
        st.caption("No audit events yet.")
    else:
        for ev in events:
            ts = ev.get("ts", "")
            t = ev.get("type", "?")
            payload = ev.get("payload", {})
            with st.expander(f"`{ts}` · **{t}**", expanded=False):
                st.code(json.dumps(payload, indent=2), language="json")
