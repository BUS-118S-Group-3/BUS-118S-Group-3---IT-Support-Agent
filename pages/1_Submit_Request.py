"""User-facing page: chat-style request entry.

End users see only this page (and the landing). They do NOT see the
audit log, ticket queue, or any administrative tools — those live on
the admin page.
"""

from __future__ import annotations

import time

import streamlit as st

from agents.orchestrator import run as run_graph
from integrations import active_directory as ad
from integrations import jira_client as jira

st.set_page_config(page_title="Submit a request", page_icon=":memo:", layout="wide")

st.markdown(
    """
    <style>
      .pillok { background:#e6f4ea;color:#1e7c2c;padding:2px 8px;border-radius:8px; }
      .pillrv { background:#fff4ce;color:#7c5b00;padding:2px 8px;border-radius:8px; }
      .pilldn { background:#fde2e2;color:#a31515;padding:2px 8px;border-radius:8px; }
      .small  { font-size: 0.85rem; color: #555; }
      .cite   { color:#555; font-size:0.8rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Submit a request")
st.caption("Describe what you need. The agent will respond in seconds.")

# ---- Sidebar: identity + examples (no admin info) ----
with st.sidebar:
    st.subheader("Sign in as")
    users = ad.list_users()
    user = st.selectbox("Identity", users, index=0, key="who")
    rec = ad.get_user(user)
    st.caption(f"{rec.get('name','')} · {rec.get('employee_type','?')} · {rec.get('department','?')}")

    st.divider()
    st.subheader("Example prompts")
    EXAMPLES = [
        ("Marketing-Public (auto)",
         "Hi, I'm starting a campaign and need access to Marketing-Public."),
        ("Sales-Pipeline (review)",
         "Please add me to Sales-Pipeline so I can review the Q3 forecast tomorrow."),
        ("Payroll-PII (compliance)",
         "I need access to Payroll-PII to finish processing this month's run."),
        ("Finance-Reports (deny)",
         "Please add me to Finance-Reports."),
        ("Legal-Contracts (contractor)",
         "Add me to Legal-Contracts so I can review the new SOW."),
    ]
    for label, txt in EXAMPLES:
        if st.button(label, use_container_width=True, key=f"ex_{label}"):
            st.session_state["pending_input"] = txt

    st.divider()
    if st.button("← Back to landing", use_container_width=True):
        st.switch_page("app.py")

# ---- Chat ----
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "last_state" not in st.session_state:
    st.session_state["last_state"] = None

for m in st.session_state["messages"]:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input("Describe what you need access to…")
if "pending_input" in st.session_state and not prompt:
    prompt = st.session_state.pop("pending_input")

if prompt:
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Routing…"):
            t0 = time.time()
            try:
                final = run_graph(prompt, requester_email=user)
            except Exception as exc:
                final = {"error": str(exc), "final_response": f"I hit an error: {exc}"}
            elapsed = time.time() - t0

        decision = final.get("decision") or "—"
        cls = {"auto_approve": "pillok", "needs_review": "pillrv", "deny": "pilldn"}.get(
            decision, "small"
        )
        st.markdown(
            f"<span class='{cls}'>{decision}</span> "
            f"<span class='small'>{elapsed:.1f}s</span>",
            unsafe_allow_html=True,
        )
        st.markdown(final.get("final_response") or "(no response)")
        cites = final.get("citations") or []
        if cites:
            st.markdown(
                "<span class='cite'>Policy basis: " + "; ".join(cites) + "</span>",
                unsafe_allow_html=True,
            )

        st.session_state["messages"].append({
            "role": "assistant",
            "content": final.get("final_response") or "(no response)",
        })
        st.session_state["last_state"] = final

# ---- Personal status: this user's pending tickets only ----
st.divider()
st.subheader("Status of your recent requests")
my_open = [
    t for t in jira.list_tickets(limit=200)
    if (t.get("metadata") or {}).get("requester_email") == user
][:10]

if not my_open:
    st.caption("No requests on file yet.")
else:
    for t in my_open:
        f = t["fields"]
        md = t.get("metadata") or {}
        status = f["status"]["name"]
        decision = md.get("decision", "—")
        target = md.get("target_resource", "?")
        st.markdown(
            f"`{t['key']}` · **{status}** · {decision} · {target}  \n"
            f"<span class='small'>{f.get('updated','')}</span>",
            unsafe_allow_html=True,
        )
