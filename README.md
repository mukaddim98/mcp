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

## Chat with a local LLM (`chat_client.py`)

`client.py` uses hard-coded inputs because there's no AI in the loop. `chat_client.py` adds one:
you type a question, a local open-source model (via [Ollama](https://ollama.com)) decides which
tool to call, the client runs it on the MCP server, and the model answers using the result.

Prerequisites: install Ollama, then pull a model that supports tool calling:

```bash
ollama pull mistral
```

Run it:

```bash
.venv\Scripts\python chat_client.py
```

Use a different model:

```bash
.venv\Scripts\python chat_client.py --model qwen3:4b
```

Example session:

```
You: What is 12.3 times 4?
  [tool] multiply({'a': 12.3, 'b': 4})
  [tool] -> 49.2
AI: 12.3 times 4 equals 49.2.
```

Notes:
- Only the server's **tools** are given to the model (not resources or prompts).
- Small models sometimes skip a tool and guess, or write the tool call as plain text.
  `chat_client.py` includes a small workaround for the latter (`recover_text_tool_calls`).
