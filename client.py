"""
A simple, basic MCP (Model Context Protocol) client.

WHAT DOES A CLIENT DO?
----------------------
In real life the client lives inside an AI application (Claude Desktop,
Claude Code, an IDE...). It connects to one or more MCP servers, asks them
what they offer (tools, resources, prompts), and then hands that list to the
AI model. When the model decides to use a tool, the client forwards the call
to the server and passes the result back to the model.

This client has no AI model - it just walks through each step by hand so you
can see exactly what happens:

    1. Launch the server (server.py) as a subprocess        -> transport
    2. Perform the "initialize" handshake                   -> session
    3. Discover what the server offers (list_* calls)
    4. Call tools, read resources, and fetch prompts

Run it with:

    python client.py
"""

import asyncio
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

# Path to the server script that sits next to this file.
SERVER_SCRIPT = Path(__file__).parent / "server.py"


async def main() -> None:
    # -----------------------------------------------------------------------
    # 1. Describe HOW to start the server
    # -----------------------------------------------------------------------
    # With the stdio transport, the client is responsible for launching the
    # server process. StdioServerParameters is simply "the command to run".
    # sys.executable = the same Python interpreter running this client, so
    # the server gets the same installed packages (including `mcp`).
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
    )

    # -----------------------------------------------------------------------
    # 2. Connect
    # -----------------------------------------------------------------------
    # Entering `async with Client(...)`:
    #   a) starts `python server.py` as a child process,
    #   b) wires its stdin/stdout up as the message channel,
    #   c) sends the "initialize" request and waits for the server's reply
    #      (this is where both sides agree on protocol version and say what
    #      features - "capabilities" - they support).
    # Leaving the `async with` block closes the connection and stops the server.
    async with Client(server_params) as client:
        print(f"Connected to server: {client.server_info.name}")
        print(f"Server instructions: {client.instructions}\n")

        # -------------------------------------------------------------------
        # 3. DISCOVERY - ask the server what it can do
        # -------------------------------------------------------------------
        # Sends a "tools/list" request. Each tool comes back with a name,
        # a description, and a JSON schema for its arguments. An AI model
        # would read exactly this information to decide which tool to call.
        tools = await client.list_tools()
        print("=== Tools ===")
        for tool in tools.tools:
            print(f"- {tool.name}: {tool.description}")
            print(f"    input schema: {tool.input_schema}")

        # "resources/list" returns the static resources (fixed URIs).
        resources = await client.list_resources()
        print("\n=== Resources ===")
        for resource in resources.resources:
            print(f"- {resource.uri}: {resource.description}")

        # "resources/templates/list" returns the parameterised ones,
        # e.g. greeting://{name}.
        templates = await client.list_resource_templates()
        print("\n=== Resource templates ===")
        for template in templates.resource_templates:
            print(f"- {template.uri_template}: {template.description}")

        # "prompts/list" returns the available prompt templates.
        prompts = await client.list_prompts()
        print("\n=== Prompts ===")
        for prompt in prompts.prompts:
            arg_names = [arg.name for arg in prompt.arguments or []]
            print(f"- {prompt.name}({', '.join(arg_names)}): {prompt.description}")

        # -------------------------------------------------------------------
        # 4. CALL A TOOL
        # -------------------------------------------------------------------
        # Sends a "tools/call" request with the tool name + arguments. The
        # server runs the Python function and returns the result as a list of
        # "content" blocks (text, images, etc.). Here it's one text block.
        print("\n=== Calling tools ===")
        result = await client.call_tool("add", {"a": 5, "b": 7})
        print(f"add(5, 7)        -> {result.content[0].text}")

        result = await client.call_tool("multiply", {"a": 3, "b": 4.5})
        print(f"multiply(3, 4.5) -> {result.content[0].text}")

        result = await client.call_tool("current_time", {})
        print(f"current_time()   -> {result.content[0].text}")

        # -------------------------------------------------------------------
        # 5. READ A RESOURCE
        # -------------------------------------------------------------------
        # Sends a "resources/read" request for a URI. The server finds the
        # matching resource (or template) and returns its contents.
        print("\n=== Reading resources ===")
        info = await client.read_resource("info://server")
        print(f"info://server    -> {info.contents[0].text}")

        # This URI matches the template greeting://{name}, so the server
        # calls get_greeting(name="Alice").
        greeting = await client.read_resource("greeting://Alice")
        print(f"greeting://Alice -> {greeting.contents[0].text}")

        # -------------------------------------------------------------------
        # 6. GET A PROMPT
        # -------------------------------------------------------------------
        # Sends a "prompts/get" request. The server fills in the template and
        # returns ready-to-use chat messages that a host app would pass to
        # the AI model.
        print("\n=== Getting a prompt ===")
        prompt = await client.get_prompt("review_code", {"code": "def f(x): return x*2"})
        for message in prompt.messages:
            print(f"[{message.role}] {message.content.text}")

    print("\nDisconnected - the server process has been shut down.")


if __name__ == "__main__":
    # MCP's Python SDK is async (it uses asyncio under the hood), so we run
    # our main() coroutine with asyncio.run().
    asyncio.run(main())
