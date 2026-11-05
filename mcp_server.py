"""
Communicates over stdio using the MCP protocol.

"""

import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# MCP server runs asynchronously — it must handle requests without blocking

# Create MCP server instance 
app = Server("calculator-server")


#Register: list_tools (MCP protocol handshake) 
@app.list_tools()
async def list_tools() -> list[Tool]:
    """MCP client calls this to discover available tools."""
    return [
        Tool(
            name="calculator",
            description="Perform addition or subtraction on two numbers.",
            inputSchema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["add", "subtract"],
                        "description": "The operation to perform: add or subtract.",
                    },
                    "a": {"type": "number", "description": "First operand."},
                    "b": {"type": "number", "description": "Second operand."},
                },
                "required": ["operation", "a", "b"],
            },
        )
    ]


# Register: call_tool (MCP protocol execution) 
@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """MCP client calls this to execute a tool."""
    if name != "calculator":
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    a  = arguments["a"]
    b  = arguments["b"]
    op = arguments["operation"]

    if op == "add":
        result = a + b
    elif op == "subtract":
        result = a - b
    else:
        return [TextContent(type="text", text=json.dumps({"error": f"Unsupported operation: {op}. Only 'add' and 'subtract' are allowed."}))]

    return [TextContent(type="text", text=json.dumps({"result": result}))]


#  Start server (listens on stdio) 
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())