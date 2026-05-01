#!/usr/bin/env bash
# One-command bootstrap for macOS / Linux.
# Creates the venv, installs dependencies, and seeds .env from the template.

set -euo pipefail

echo
echo "=== folder_access_agent setup ==="
echo

# ---- Step 1: confirm Python is available ----
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 was not found on your PATH."
    echo
    echo "Install Python 3.10 or newer:"
    echo "  macOS:   brew install python@3.12"
    echo "  Ubuntu:  sudo apt install python3.12 python3.12-venv"
    echo
    exit 1
fi

# ---- Step 2: create the virtual environment ----
if [ -x .venv/bin/python ]; then
    echo "[1/3] Virtual environment already exists, skipping creation."
else
    echo "[1/3] Creating virtual environment in .venv ..."
    python3 -m venv .venv
fi

# ---- Step 3: install dependencies ----
echo "[2/3] Installing dependencies (this takes a couple of minutes the first time) ..."
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt

# ---- Step 4: seed .env if missing ----
if [ -f .env ]; then
    echo "[3/3] .env already exists, leaving it alone."
else
    echo "[3/3] Creating .env from .env.example ..."
    cp .env.example .env
fi

cat <<'EOF'

============================================================
 Setup complete.

 Next steps:

   1. Open .env and set your OpenAI API key:
        nano .env       # or your editor of choice

   2. Build the policy index (one-time, needs your API key):
        python -m rag.ingest

   3. Start the app:
        streamlit run app.py

 Whenever you open a new shell to work on this project,
 re-activate the venv first:
        source .venv/bin/activate
============================================================
EOF
