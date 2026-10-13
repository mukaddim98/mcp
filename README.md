# Simple MCP Server + Client (Python)

A minimal, heavily commented example of the Model Context Protocol (MCP).

| File        | What it is |
|-------------|------------|
| `server.py` | An MCP server exposing **tools** (`add`, `multiply`, `current_time`), **resources** (`info://server`, `greeting://{name}`), and a **prompt** (`review_code`). |
| `client.py` | An MCP client that launches the server, does the handshake, lists everything, and calls each feature. |

## How it fits together

```
client.py                                server.py
---------                                ---------
starts "python server.py"  ───────────▶  process starts, waits on stdin
initialize                 ───stdin──▶   reply with name + capabilities
tools/list                 ───stdin──▶   list of tools + JSON schemas
tools/call add {a:5,b:7}   ───stdin──▶   runs add(5, 7)
                           ◀──stdout───  result: 12
close connection           ───────────▶  process exits
```

All messages are JSON-RPC 2.0 sent over the server's stdin/stdout ("stdio transport").

## Setup & run

```bash
python -m venv .venv
```

```bash
.venv\Scripts\pip install -r requirements.txt
```

```bash
.venv\Scripts\python client.py
```

## Use the server from Claude Code

```bash
claude mcp add demo-server -- C:\Users\ab845312\Downloads\github\mcp\.venv\Scripts\python.exe C:\Users\ab845312\Downloads\github\mcp\server.py
```
