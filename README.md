# Automated Folder/Directory Access Provisioning

A multi-agent system that automates the IT support workflow for granting,
denying, or escalating access requests to shared folders and AD groups.

Built with **LangGraph**, **OpenAI GPT-4**, and **ChromaDB** for RAG.

## Architecture

```
                       ┌─────────────────┐
   User request ─────► │  Intake Agent   │  classify + extract entities
                       └────────┬────────┘
                                │
                       ┌────────▼────────┐
                       │ Knowledge Agent │  RAG over policy KB → recommendation
                       └────────┬────────┘
                                │
                          (router decides)
                  ┌─────────────┼─────────────┐
                  ▼             ▼             ▼
           ┌──────────┐  ┌────────────┐  ┌────────────┐
           │ Workflow │  │ Escalation │  │ Escalation │
           │  (auto)  │  │  (review)  │  │   (deny)   │
           └────┬─────┘  └──────┬─────┘  └──────┬─────┘
                │               │               │
                └───────────────┼───────────────┘
                                ▼
                        Final response + audit log
```

### Agents

| Agent       | Responsibility                                          | Tools                          |
|-------------|---------------------------------------------------------|--------------------------------|
| Intake      | Parse free-text request → structured fields, classify   | LLM only                       |
| Knowledge   | Retrieve policies (RAG) + recommend action              | ChromaDB, embeddings, LLM      |
| Workflow    | Execute provisioning, audit, notify ticketing system    | Mock AD, mock Jira, audit log  |
| Escalation  | Route to humans, draft tickets, communicate decisions   | Mock Jira, audit log, LLM      |

## Clone and Run (fastest path)

If you have Python 3.10+ and Git installed, this is the whole setup:

**Windows (Command Prompt):**
```cmd
git clone https://github.com/YOUR_USERNAME/folder_access_agent.git
cd folder_access_agent
setup.bat
notepad .env
.venv\Scripts\activate.bat
python -m rag.ingest
streamlit run app.py
```

**macOS / Linux:**
```bash
git clone https://github.com/YOUR_USERNAME/folder_access_agent.git
cd folder_access_agent
chmod +x setup.sh && ./setup.sh
nano .env
source .venv/bin/activate
python -m rag.ingest
streamlit run app.py
```

The `setup` script creates the virtual environment, installs every
dependency, and copies `.env.example` to `.env`. You only need to do
two things by hand: paste your `OPENAI_API_KEY` into `.env`, and run
the one-time RAG index build.

## Quick Start (manual, step by step)

If you'd rather see what each step does:

### 1. Install

```bash
cd folder_access_agent
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate.bat
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env         # Windows cmd: copy .env.example .env
# Edit .env and set OPENAI_API_KEY
```

### 3. Build the RAG index

```bash
python -m rag.ingest
```

This embeds the markdown files in `knowledge_base/` into a local Chroma index.

### 4. Run the demo

**Streamlit UI** (recommended for demos):
```bash
streamlit run app.py
```

**CLI demo** (good for testing):
```bash
python run_demo.py
```

**Run the test scenarios**:
```bash
pytest tests/ -v
```

## Two Surfaces

The Streamlit app has two clearly separated pages — end users only ever
see the request page; the audit log and human-intervention controls
live behind the admin dashboard.

| Page                       | Who                  | What                                                      |
|----------------------------|----------------------|-----------------------------------------------------------|
| `app.py` (landing)         | Anyone               | Pick "I need access" or "I'm IT support"                  |
| `pages/1_Submit_Request.py`| End users            | Chat-style request entry; status of *their own* requests  |
| `pages/2_IT_Admin.py`      | IT / Compliance team | Pending escalation queue, approve/deny, full audit log    |

The same logic is also exposed over **MCP** (`mcp_server.py`) so Claude
Desktop or any MCP client can drive it. See `docs/MCP_SETUP.md`.

## Project Layout

```
folder_access_agent/
├── app.py                      # Landing page
├── pages/
│   ├── 1_Submit_Request.py     # End-user chat
│   └── 2_IT_Admin.py           # Admin dashboard (queue + audit + actions)
├── mcp_server.py               # MCP server (stdio) — Claude Desktop integration
├── run_demo.py                 # CLI demo runner
├── config.py                   # Settings + env loading
├── agents/
│   ├── state.py                # Shared LangGraph state
│   ├── intake.py               # Intake Agent
│   ├── knowledge.py            # Knowledge Agent (RAG)
│   ├── workflow.py             # Workflow Agent
│   ├── escalation.py           # Escalation Agent
│   ├── admin_actions.py        # Human-in-the-loop approve/deny/reassign
│   └── orchestrator.py         # LangGraph builder
├── rag/
│   ├── ingest.py               # Build Chroma index
│   └── retriever.py            # Query Chroma
├── integrations/
│   ├── active_directory.py     # Mock AD adapter
│   ├── jira_client.py          # Mock Jira adapter (with status transitions)
│   └── audit_log.py            # JSONL audit log
├── knowledge_base/             # Markdown policy docs (the RAG corpus)
├── data/                       # Mock users / groups / tickets / audit log
├── docs/
│   ├── ARCHITECTURE.md
│   ├── UX_WIREFRAMES.md
│   ├── METRICS.md
│   └── MCP_SETUP.md            # Claude Desktop integration walkthrough
└── tests/
    └── test_scenarios.py
```

## How RAG Grounds the Agents

The Knowledge Agent never answers from the LLM's parametric memory. Every
policy claim is grounded in a chunk retrieved from ChromaDB and surfaced to
the user as a citation. This is the primary defense against hallucinated
"policy" that doesn't exist in your actual SOPs.

The corpus in `knowledge_base/` is a small but realistic IT policy set:
access policies, compliance rules (SOX/PII/HIPAA), the AD group catalog,
escalation runbooks, and an FAQ. Replace these markdown files with your
real policy library to point the system at production data.

## Mocked Integrations

`integrations/active_directory.py` and `integrations/jira_client.py` are
realistic stubs: they read/write `data/groups.json` and `data/tickets.json`
and emit the same data shapes a real adapter would. Swap them for real
LDAP/Jira clients without changing any agent code.

## Why This Design

**Separation of concerns** — Each agent has one job. Adding a new
compliance check means a new node in the graph, not a new branch in a
1,000-line function.

**Auditability** — Every state transition writes to `audit_log.jsonl`.
Compliance can replay any decision and see which policy chunks were
retrieved and which agent made which call.

**Swap-friendly** — LLM provider, vector DB, and integrations are behind
small interfaces. Move from ChromaDB to Pinecone or from mock AD to real
LDAP without touching the agent layer.

## Reference

See `docs/ARCHITECTURE.md` for the full agent contract, `docs/UX_WIREFRAMES.md`
for the UI mockups, and `docs/METRICS.md` for how to measure success.

## Publishing this to your own GitHub

The repo is set up to be portable: a `.gitignore` keeps secrets,
generated state, and the venv out of the commit, while the seed mock
data (`data/users.json`, `data/groups.json`) stays in so anyone who
clones gets a working demo immediately.

### One-time: create the repo

1. Sign in at https://github.com and click **New repository** (top right `+` menu).
2. Name it (e.g. `folder_access_agent`), leave it empty (no README, no license — you have those already), and create it.
3. GitHub will show a "push an existing repository" snippet. The four commands below are the same idea, run from inside your project folder.

### Push your code

From inside the project folder:

```bash
git init
git add .
git commit -m "Initial commit: multi-agent folder access provisioning"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/folder_access_agent.git
git push -u origin main
```

You'll be prompted for credentials. On Windows the easiest path is to
install [GitHub CLI](https://cli.github.com/) and run `gh auth login`
once — after that, `git push` just works.

### What gets uploaded vs. what stays local

| Committed (safe to share) | Ignored (stays on your machine)            |
|---------------------------|--------------------------------------------|
| All source code           | `.venv/` (your virtual environment)        |
| `knowledge_base/*.md`     | `.env` (your OpenAI key — never commit!)   |
| `data/users.json`         | `chroma_store/` (regenerated by `ingest`)  |
| `data/groups.json`        | `data/audit_log.jsonl` (runtime audit)     |
| `.env.example` (template) | `data/tickets.json` (runtime ticket state) |
| `setup.bat`, `setup.sh`   | `__pycache__/` (Python caches)             |
| `requirements.txt`        |                                            |
| `README.md` and `docs/`   |                                            |

### Sharing it

Anyone you share the repo with runs the same three lines from the
**Clone and Run** section at the top of this README and they're up
in five minutes. They need their own OpenAI API key — the project
is configured to fail loudly if `OPENAI_API_KEY` isn't set, so
nobody can accidentally use yours.

### Pulling future changes

When you make edits and want to push:
```bash
git add .
git commit -m "Describe what changed"
git push
```

When others (or future-you on a different machine) want the latest:
```bash
git pull
```

If `requirements.txt` changed in a pull, re-run `pip install -r requirements.txt`
inside the venv to pick up new dependencies.
