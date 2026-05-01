# Connect to Claude Desktop via MCP

This system exposes itself as a Model Context Protocol (MCP) server, so
Claude Desktop (or any MCP client) can drive the same tools the
Streamlit UI uses — submitting requests, listing pending escalations,
approving/denying tickets, reading the audit log.

## What you'll be able to do once it's wired up

In a normal Claude Desktop chat you can say things like:

> "What access requests are waiting for me?"
> → Claude calls `list_pending_escalations` and shows the queue.

> "Approve ITACCESS-12 with note 'verified with the data owner'."
> → Claude calls `approve_escalation`, the AD grant fires, the ticket closes.

> "Submit a request for alice.nguyen@acme.example: she needs Marketing-Public for a campaign."
> → Claude calls `request_access`, the multi-agent flow runs, the result comes back.

## Prerequisites

1. The project is set up and you've run `pip install -r requirements.txt`
   (the install includes the `mcp` Python package).
2. Your `.env` has a working `OPENAI_API_KEY`.
3. You've run `python -m rag.ingest` once.
4. **Claude Desktop is installed** (https://claude.ai/download).

## Find your config file

Claude Desktop stores MCP server config in a JSON file:

| OS       | Path                                                                 |
|----------|----------------------------------------------------------------------|
| Windows  | `%APPDATA%\Claude\claude_desktop_config.json`                        |
| macOS    | `~/Library/Application Support/Claude/claude_desktop_config.json`    |

If the file doesn't exist yet, create it.

## Add this server

Open the config file and add an entry under `mcpServers`:

### Windows example

```json
{
  "mcpServers": {
    "access-provisioning": {
      "command": "C:\\Users\\terre\\projects\\folder_access_agent\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\Users\\terre\\projects\\folder_access_agent\\mcp_server.py"
      ]
    }
  }
}
```

> **Important**: use the Python from the project's virtual environment
> (the `.venv\Scripts\python.exe` path), not your system Python.
> Otherwise the server starts up but can't find `langgraph`,
> `chromadb`, etc.
>
> All backslashes in JSON must be doubled (`\\`).

### macOS / Linux example

```json
{
  "mcpServers": {
    "access-provisioning": {
      "command": "/Users/you/projects/folder_access_agent/.venv/bin/python",
      "args": [
        "/Users/you/projects/folder_access_agent/mcp_server.py"
      ]
    }
  }
}
```

### Multiple servers

If you already have other MCP servers configured, just add a new key
inside `mcpServers` — don't replace the whole block:

```json
{
  "mcpServers": {
    "filesystem": { ... existing ... },
    "access-provisioning": {
      "command": "...",
      "args": ["..."]
    }
  }
}
```

## Restart Claude Desktop

MCP config is read at startup. Fully quit the app (right-click the
system tray icon → Quit, not just close the window) and reopen it.

## Verify the connection

In a new Claude Desktop chat, look for the tools indicator (a small
icon near the input bar) and confirm you see tools prefixed with
`access-provisioning`. You should see:

- `request_access`
- `lookup_user`
- `lookup_group`
- `list_groups`
- `list_pending_escalations`
- `approve_escalation`
- `deny_escalation`
- `reassign_escalation`
- `read_audit_log`
- `dashboard_stats`
- `get_ticket`

Then try a simple smoke test — type into Claude Desktop:

> Use the access-provisioning tools to look up alice.nguyen@acme.example.

Claude should call `lookup_user` and show you Alice's record.

## Common issues

**"MCP server failed to start"** — almost always wrong Python or wrong
path. Open a terminal and run the exact command/args from the JSON
manually. If that fails with an `ImportError`, the venv path is wrong.

**"Tools don't show up after restart"** — Windows tray-quit is required;
closing the window only minimizes. Also check the JSON is valid (no
trailing commas, all paths escaped).

**"Permission denied" on macOS** — `chmod +x mcp_server.py` and re-add
the server.

**Edits to my Python files don't show up** — Claude Desktop spawns the
server once on startup. Quit and relaunch to pick up code changes.

## Going further

- The same `mcp_server.py` works with VS Code's Continue extension and
  with `mcp-remote` — you don't need a separate server per client.
- To add a new tool, decorate a function in `mcp_server.py` with
  `@mcp.tool()`. The docstring becomes the tool description Claude
  sees, so write it like a function reference, not a marketing line.
- The agent layer (`agents/*.py`) is unchanged — the MCP server is a
  thin facade over the same `run_graph()` and `admin_actions` calls
  the Streamlit UI uses.
