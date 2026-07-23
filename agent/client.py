import sys
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool

# Same launch pattern as scripts/test_mcp_tools.py: sys.executable guarantees
# we launch the interpreter (and virtual environment) currently running,
# regardless of what "python" resolves to on PATH.
SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["-m", "mcp_server.server"],
)


@asynccontextmanager
async def mcp_session():
    """Launches the MCP server as a subprocess and yields a live,
    initialized ClientSession connected to it. One session is opened for an
    entire agent task (not re-opened per tool call) - subprocess startup has
    real overhead, and a task's tool calls have no reason to each pay it.
    The subprocess is terminated automatically when the `async with` block
    around this exits."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def mcp_tool_to_groq_tool(tool: Tool) -> dict:
    """Translate one MCP Tool's schema into the tool-calling format Groq's
    (OpenAI-compatible) API expects. Both ultimately describe a function's
    parameters as JSON Schema - only the envelope differs."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
    }
