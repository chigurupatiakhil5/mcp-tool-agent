import os
import sys
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool

# sys.executable guarantees we launch the interpreter (and virtual
# environment, or in Docker, the container's own Python) currently running,
# regardless of what "python" resolves to on PATH.
#
# env=dict(os.environ): by default StdioServerParameters gives the spawned
# process only a restricted allow-list of environment variables, not the
# full parent environment - a sensible default for launching an arbitrary
# third-party MCP server, but wrong here, where the "server" is our own
# trusted code that needs the same POSTGRES_*/GROQ_* config we have. This
# bug existed since v3 without being noticed: on the host, app/config.py
# falls back to reading the .env FILE directly from disk regardless of
# inherited env vars, which papered over the missing environment - but
# there's no .env file inside a Docker container (v6), only real injected
# environment variables, which is what finally exposed it.
SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["-m", "mcp_server.server"],
    env=dict(os.environ),
)


@asynccontextmanager
async def mcp_session():
    """Launches the MCP server as a subprocess and yields a live,
    initialized ClientSession connected to it. One session is opened for an
    entire agent task (not re-opened per tool call) - subprocess startup has
    real overhead, and a task's tool calls have no reason to each pay it.
    The subprocess is terminated automatically when the `async with` block
    around this exits."""
    async with stdio_client(SERVER_PARAMS) as (read, write), ClientSession(read, write) as session:
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
