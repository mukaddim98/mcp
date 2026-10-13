"""
A simple, basic MCP (Model Context Protocol) server.

WHAT IS MCP?
------------
MCP is an open protocol that lets AI applications (the "client" / "host",
e.g. Claude Desktop, Claude Code, or our own client.py) talk to external
programs (the "server") in a standard way. Under the hood, client and server
exchange JSON-RPC 2.0 messages such as:

    client -> server:  {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    server -> client:  {"jsonrpc": "2.0", "id": 1, "result": {"tools": [...]}}

A server can expose three main kinds of things ("primitives"):

  1. TOOLS     - functions the AI can CALL to do something (like an API endpoint).
                 e.g. "add two numbers", "send an email", "query a database".
  2. RESOURCES - read-only DATA the AI can READ, identified by a URI.
                 e.g. "file://notes.txt", "config://app".
  3. PROMPTS   - reusable prompt TEMPLATES the user can pick from.

This file defines a server with a couple of each, using the official
Python SDK's high-level `MCPServer` class (it was called `FastMCP` in mcp 1.x).
MCPServer reads your Python type hints and docstrings and turns them into the
JSON schemas / descriptions the protocol needs, so you just write normal
Python functions.

HOW DOES IT RUN?
----------------
We use the "stdio" transport: the client launches this script as a child
process and sends JSON-RPC messages over its stdin, reading replies from its
stdout. That's why you should NEVER use print() in an stdio server - anything
printed to stdout would corrupt the protocol stream. (Logging to stderr is fine.)

You normally don't run this file yourself; client.py starts it for you.
"""

from datetime import datetime

from mcp.server.mcpserver import MCPServer

# ---------------------------------------------------------------------------
# 1. Create the server
# ---------------------------------------------------------------------------
# The name is sent to the client during the "initialize" handshake so the
# client knows who it's talking to. `instructions` is optional text that
# tells the AI model how/when to use this server.
mcp = MCPServer(
    name="demo-server",
    instructions="A tiny demo server with math tools, a greeting resource, and a review prompt.",
)


# ---------------------------------------------------------------------------
# 2. TOOLS - functions the AI model can call
# ---------------------------------------------------------------------------
# The @mcp.tool() decorator registers the function as a tool.
#   - The function name becomes the tool name ("add").
#   - The docstring becomes the tool's description (the AI reads this to
#     decide WHEN to use the tool, so make it clear!).
#   - The type hints (a: int, b: int) become the tool's JSON "inputSchema",
#     which tells the client what arguments to send.
#   - The return value is sent back to the client as the tool result.
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers together and return the sum."""
    return a + b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers and return the product."""
    return a * b


@mcp.tool()
def current_time() -> str:
    """Return the server's current local date and time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# 3. RESOURCES - read-only data, addressed by a URI
# ---------------------------------------------------------------------------
# A STATIC resource: always the same URI, the client reads it with
# read_resource("info://server").
@mcp.resource("info://server")
def server_info() -> str:
    """Basic information about this demo server."""
    return "This is demo-server, a minimal MCP server written in Python."


# A resource TEMPLATE: the {name} placeholder in the URI becomes a function
# argument. Reading "greeting://Alice" calls get_greeting(name="Alice").
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Return a personalised greeting for the given name."""
    return f"Hello, {name}! Welcome to MCP."


# ---------------------------------------------------------------------------
# 4. PROMPTS - reusable prompt templates
# ---------------------------------------------------------------------------
# A prompt returns text (or a list of messages) that the client can insert
# into a conversation with the AI. Arguments let the user fill in the blanks.
@mcp.prompt()
def review_code(code: str) -> str:
    """Ask the AI to review a piece of code."""
    return f"Please review the following code and suggest improvements:\n\n{code}"


# ---------------------------------------------------------------------------
# 5. Start the server
# ---------------------------------------------------------------------------
# mcp.run() starts listening on stdin/stdout (the default "stdio" transport)
# and keeps running until the client disconnects. It automatically handles
# the protocol for you:
#   - "initialize"      -> handshake: exchange names, versions, capabilities
#   - "tools/list"      -> returns the tools registered above
#   - "tools/call"      -> runs the matching Python function
#   - "resources/list", "resources/read", "prompts/list", "prompts/get", ...
if __name__ == "__main__":
    mcp.run()  # same as mcp.run(transport="stdio")
