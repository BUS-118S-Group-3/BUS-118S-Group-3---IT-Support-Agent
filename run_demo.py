"""CLI demo runner.

Walks through the canonical scenarios end-to-end without the Streamlit UI.

Usage:
    python -m rag.ingest        # one-time, builds the Chroma index
    python run_demo.py
"""

from __future__ import annotations

import textwrap
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from agents.orchestrator import run as run_graph

console = Console()

SCENARIOS = [
    {
        "label": "Low-risk auto-approve (Marketing-Public)",
        "user": "alice.nguyen@acme.example",
        "msg": "Hi, I'm starting a new campaign and need access to Marketing-Public.",
    },
    {
        "label": "Medium tier — manager review (Sales-Pipeline)",
        "user": "alice.nguyen@acme.example",
        "msg": "Please add me to Sales-Pipeline so I can review the Q3 forecast.",
    },
    {
        "label": "Restricted — compliance review (Payroll-PII)",
        "user": "bob.singh@acme.example",
        "msg": "I need access to Payroll-PII to finish processing this month.",
    },
    {
        "label": "SoD violation (Fiona already in Finance-Approvers, asks for Finance-Reports)",
        "user": "fiona.reed@acme.example",
        "msg": "Please add me to Finance-Reports so I can pull the board pack.",
    },
    {
        "label": "Contractor + employees-only (Evan asks for Legal-Contracts)",
        "user": "evan.park@acme.example",
        "msg": "Add me to Legal-Contracts so I can review the SOW.",
    },
    {
        "label": "Recent for-cause revoke (Hana asks for Engineering-Secrets)",
        "user": "hana.kim@acme.example",
        "msg": "I need Engineering-Secrets again to finish the deploy.",
    },
    {
        "label": "Missing training (Gus's training is stale)",
        "user": "gus.olsen@acme.example",
        "msg": "Add me to Sales-Pipeline.",
    },
]


def _short(text: str, width: int = 100) -> str:
    return textwrap.shorten(text or "", width=width, placeholder="…")


def render(scenario: dict[str, Any], state: dict[str, Any]) -> None:
    decision = state.get("decision", "—")
    risk = state.get("risk_tier", "—")
    action = state.get("action_taken", "—")
    ticket = state.get("ticket_key") or "—"
    citations = "; ".join(state.get("citations") or []) or "(none)"

    body = (
        f"[bold]User:[/bold] {scenario['user']}\n"
        f"[bold]Message:[/bold] {scenario['msg']}\n\n"
        f"[bold]Decision:[/bold] {decision}   "
        f"[bold]Risk tier:[/bold] {risk}\n"
        f"[bold]Action:[/bold] {action}\n"
        f"[bold]Ticket:[/bold] {ticket}\n"
        f"[bold]Citations:[/bold] {citations}\n\n"
        f"[bold]Rationale:[/bold] {_short(state.get('decision_rationale',''), 240)}\n\n"
        f"[bold]Reply to user:[/bold]\n{state.get('final_response','')}\n"
    )
    console.print(Panel(body, title=scenario["label"], border_style="cyan"))


def main() -> int:
    for sc in SCENARIOS:
        console.print(Rule(style="dim"))
        try:
            state = run_graph(sc["msg"], requester_email=sc["user"])
        except Exception as exc:
            console.print(f"[red]ERROR[/red] {sc['label']}: {exc}")
            continue
        render(sc, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
