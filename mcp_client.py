"""
Flow:
  1. Spawns mcp_server.py as a subprocess (stdio transport).
  2. Uses MCP protocol to discover tools from the server.
  3. Passes discovered tools to Claude API.
  4. When Claude calls a tool, forwards it to the MCP server via protocol.
  5. Loops until Claude gives a final text answer.

"""
import asyncio
import os
import json
import anthropic

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# Config 

MODEL   = "claude-sonnet-4-20250514"
MAX_TOK = 1024


# Helpers 

def mcp_tool_to_anthropic(mcp_tool) -> dict:
    """Convert an MCP Tool object → Anthropic tool schema dict."""
    return {
        "name": mcp_tool.name,
        "description": mcp_tool.description,
        "input_schema": mcp_tool.inputSchema,
    }


# Main client logic 

async def run(user_message: str):
    anthropic_client = anthropic.Anthropic(api_key="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")

    # Launch mcp_server.py as a subprocess over stdio 
    server_params = StdioServerParameters(
        command="python",
        args=["mcp_server.py"],   # server file must be in the same directory
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as mcp_session:

            # MCP handshake — initialise the session 
            await mcp_session.initialize()
            print("\n[MCP] Session initialised with server")

            #  Discover tools via MCP protocol 
            tools_response = await mcp_session.list_tools()
            tools = [mcp_tool_to_anthropic(t) for t in tools_response.tools]

            print(f"[MCP] Tools discovered: {[t['name'] for t in tools]}")

            # First call to Claude with discovered tools 
            messages = [{"role": "user", "content": user_message}]

            print(f"User  ▶  {user_message}")

            response = anthropic_client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOK,
                tools=tools,
                messages=messages,
            )

            print(f"\nClaude stop reason: {response.stop_reason}")

            # Loop — forward every tool call to MCP server ──────────
            while response.stop_reason == "tool_use":
                assistant_content = response.content
                tool_results = []

                for block in assistant_content:
                    if block.type == "tool_use":
                        print(f"\n[MCP] Claude called tool : {block.name}")
                        print(f"[MCP] Tool input         : {json.dumps(block.input, indent=2)}")

                        # This is the real MCP protocol call 
                        mcp_result = await mcp_session.call_tool(block.name, block.input)
                        raw_result = mcp_result.content[0].text
                        print(f"[MCP] Tool result        : {raw_result}")

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": raw_result,
                        })

                # Feed results back to Claude
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user",      "content": tool_results})

                response = anthropic_client.messages.create(
                    model=MODEL,
                    max_tokens=MAX_TOK,
                    tools=tools,
                    messages=messages,
                )

                print(f"\nClaude stop reason: {response.stop_reason}")

            # Print final answer 
            final_answer = "".join(
                block.text for block in response.content if hasattr(block, "text")
            )

            print(f"\nClaude ▶  {final_answer}")
            return final_answer


# Entry point 

if __name__ == "__main__":
    asyncio.run(run("Add 128 and 74, then subtract 35 from the result."))