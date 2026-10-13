"""
An interactive MCP client powered by a LOCAL open-source LLM (via Ollama).

client.py showed the protocol step by step with hard-coded inputs. This file
shows how MCP is used for real: YOU type a question in plain English, an AI
model decides which tool (if any) to call and with what arguments, the client
runs that tool on the MCP server, and the model uses the result to answer.

    You ──question──▶ chat_client.py ──messages + tool list──▶ LLM (Ollama)
                            │                                     │
                            │◀──"please call add(a=5, b=7.5)"─────┘
                            │
                            ├──tools/call add {a:5, b:7.5}──▶ server.py
                            │◀──────────────── 12.5 ──────────┘
                            │
                            ├──tool result "12.5"──────────▶ LLM
    You ◀──"5 + 7.5 is 12.5"┘◀──────── final answer ──────────┘

Notice the LLM never talks to the server directly. It only *asks* for a tool
call; the client is the one that actually executes it. The client is the
middleman between the model and the MCP server(s).

PREREQUISITES
-------------
  1. Ollama installed and running (https://ollama.com).
  2. A model that supports tool calling, e.g.:   ollama pull mistral
  3. Python packages:                            pip install -r requirements.txt

Run it with:

    python chat_client.py                  # uses mistral
    python chat_client.py --model qwen3:4b # or any other tool-capable model
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import ollama
from mcp import Client, StdioServerParameters

SERVER_SCRIPT = Path(__file__).parent / "server.py"

# The "system prompt" sets the model's behaviour for the whole conversation.
# Small models sometimes guess instead of using a tool, so we nudge them.
SYSTEM_PROMPT = (
    "You are a helpful assistant with access to tools. "
    "Use the tools for arithmetic and for the current time instead of guessing. "
    "For normal conversation, just reply without calling a tool."
)


def mcp_tool_to_ollama(tool) -> dict:
    """Convert an MCP tool description into the format Ollama expects.

    Both use the same idea - a name, a description, and a JSON schema for the
    arguments - just wrapped slightly differently. MCP's `input_schema` is
    already a JSON schema, so it can be passed straight through.
    """
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
        },
    }


def recover_text_tool_calls(message: ollama.Message, tool_names: set[str]) -> ollama.Message:
    """Workaround for small models that write tool calls as plain text.

    Normally Ollama recognises a tool call and puts it in `message.tool_calls`.
    Some models (notably mistral 7B) sometimes skip the special marker and just
    write the JSON into the reply, e.g.:

        [{"name": "multiply", "arguments": {"a": 12.3, "b": 4}}]
        12.3 * 4 = 49.2      <- a guess, written before the tool even ran

    If the reply starts with JSON like that, we turn it into proper tool calls
    (and drop the guessed text). If the JSON names a tool that doesn't exist,
    we strip the JSON and keep only the text after it.
    """
    content = (message.content or "").strip()
    if message.tool_calls or not content.startswith(("[", "{")):
        return message

    try:
        parsed, end = json.JSONDecoder().raw_decode(content)
    except json.JSONDecodeError:
        return message

    calls = parsed if isinstance(parsed, list) else [parsed]
    valid = [c for c in calls if isinstance(c, dict) and c.get("name") in tool_names]
    if not valid:
        return ollama.Message(role="assistant", content=content[end:].strip())

    return ollama.Message(
        role="assistant",
        content="",
        tool_calls=[
            ollama.Message.ToolCall(
                function=ollama.Message.ToolCall.Function(name=c["name"], arguments=c.get("arguments") or {})
            )
            for c in valid
        ],
    )


def result_to_text(result) -> str:
    """Flatten an MCP tool result (a list of content blocks) into plain text."""
    texts = [block.text for block in result.content if getattr(block, "text", None) is not None]
    text = "\n".join(texts) if texts else "(no output)"
    # If the tool failed (e.g. bad arguments), tell the model so it can recover.
    return f"Error: {text}" if result.is_error else text


async def chat(model: str) -> None:
    llm = ollama.AsyncClient()  # talks to the local Ollama server (http://localhost:11434)

    server_params = StdioServerParameters(command=sys.executable, args=[str(SERVER_SCRIPT)])

    # -----------------------------------------------------------------------
    # 1. Connect to the MCP server and discover its tools (same as client.py)
    # -----------------------------------------------------------------------
    async with Client(server_params) as mcp_client:
        mcp_tools = (await mcp_client.list_tools()).tools

        # ...and translate them so the LLM knows what it is allowed to call.
        llm_tools = [mcp_tool_to_ollama(t) for t in mcp_tools]
        tool_names = {t.name for t in mcp_tools}

        print(f"Connected to MCP server '{mcp_client.server_info.name}'.")
        print(f"Tools available to the model: {', '.join(t.name for t in mcp_tools)}")
        print(f"Model: {model}   (type 'quit' to exit)\n")

        # The conversation history. LLMs are stateless: every request sends the
        # whole conversation so far, so we keep appending to this list.
        messages: list = [{"role": "system", "content": SYSTEM_PROMPT}]

        while True:
            # ---------------------------------------------------------------
            # 2. Read what the user types
            # ---------------------------------------------------------------
            # input() blocks, so run it in a thread to keep the async MCP
            # connection responsive in the background.
            try:
                user_text = (await asyncio.to_thread(input, "You: ")).strip()
            except (EOFError, KeyboardInterrupt):
                break
            if user_text.lower() in {"quit", "exit"}:
                break
            if not user_text:
                continue

            messages.append({"role": "user", "content": user_text})

            # ---------------------------------------------------------------
            # 3. Ask the model, giving it the list of tools it may use
            # ---------------------------------------------------------------
            try:
                response = await llm.chat(model=model, messages=messages, tools=llm_tools)
            except ollama.ResponseError as e:
                print(f"Ollama error: {e.error}  (did you run 'ollama pull {model}'?)\n")
                messages.pop()
                continue
            except ConnectionError:
                print("Could not reach Ollama. Is it running? (start the Ollama app)\n")
                messages.pop()
                continue

            # ---------------------------------------------------------------
            # 4. The tool-calling loop
            # ---------------------------------------------------------------
            # If the model wants to use tools, its reply contains `tool_calls`
            # instead of (or as well as) a normal answer. We run each call on
            # the MCP server, add the results to the conversation, and ask the
            # model again. This repeats until the model replies with plain text.
            response.message = recover_text_tool_calls(response.message, tool_names)
            while response.message.tool_calls:
                messages.append(response.message)  # remember what the model asked for

                for call in response.message.tool_calls:
                    name = call.function.name
                    args = call.function.arguments
                    print(f"  [tool] {name}({args})")

                    # This is the MCP part: a "tools/call" request to server.py.
                    result = await mcp_client.call_tool(name, args)
                    output = result_to_text(result)
                    print(f"  [tool] -> {output}")

                    # Hand the result back to the model as a "tool" message.
                    messages.append({"role": "tool", "content": output, "tool_name": name})

                response = await llm.chat(model=model, messages=messages, tools=llm_tools)
                response.message = recover_text_tool_calls(response.message, tool_names)

            # ---------------------------------------------------------------
            # 5. Show the model's final answer and keep it in the history
            # ---------------------------------------------------------------
            messages.append(response.message)
            print(f"AI: {response.message.content}\n")

    print("Bye - the MCP server has been shut down.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chat with the MCP demo server through a local LLM.")
    parser.add_argument("--model", default="mistral", help="Ollama model name (must support tools)")
    asyncio.run(chat(parser.parse_args().model))
