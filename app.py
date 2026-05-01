"""Landing page — picks between the user request flow and the IT admin dashboard.

Run with:    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Access Provisioning",
    page_icon=":lock:",
    layout="centered",
)

st.markdown(
    """
    <style>
      .role-card {
          padding: 24px;
          border: 1px solid #e2e2e2;
          border-radius: 12px;
          background: #fafafa;
          height: 100%;
      }
      .role-title { font-size: 1.3rem; font-weight: 600; margin-bottom: 8px; }
      .role-sub { color: #555; font-size: 0.95rem; margin-bottom: 16px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Automated Access Provisioning")
st.caption(
    "Multi-agent IT support: Intake → Knowledge (RAG) → Workflow / Escalation"
)

st.write("")
st.write("Who's using the system right now?")

col_user, col_admin = st.columns(2)

with col_user:
    st.markdown(
        "<div class='role-card'>"
        "<div class='role-title'>I need access</div>"
        "<div class='role-sub'>Submit a request in plain English. The agent "
        "decides whether to grant it, route it for review, or deny it.</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    if st.button("Open request page", use_container_width=True, type="primary"):
        st.switch_page("pages/1_Submit_Request.py")

with col_admin:
    st.markdown(
        "<div class='role-card'>"
        "<div class='role-title'>I'm IT support</div>"
        "<div class='role-sub'>Review the escalation queue, approve or deny "
        "pending tickets, and inspect the full audit log.</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    if st.button("Open admin dashboard", use_container_width=True):
        st.switch_page("pages/2_IT_Admin.py")

st.write("")
st.divider()
with st.expander("How it works"):
    st.markdown(
        """
        1. **Intake Agent** parses your free-text request into structured fields.
        2. **Knowledge Agent** does RAG over the policy KB and recommends
           one of: *auto-approve*, *needs review*, or *deny*.
        3. **Workflow Agent** executes auto-approvals against a mock AD.
        4. **Escalation Agent** files a Jira-shaped ticket and routes
           non-auto cases to the right human.

        End users only ever see the **request page**. Everything else —
        the audit log, the queue, manual approval — lives behind the
        **admin dashboard**.
        """
    )
