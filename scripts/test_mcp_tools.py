"""Manual smoke test for the MCP server - connects to it exactly the way
Claude Desktop (and, later, our own agent) will: as a client, over stdio,
launching the server as a subprocess. Run from the project root with:

    python -m scripts.test_mcp_tools

This is not an automated test suite (that comes in v6) - it's a quick way to
prove a tool actually works end-to-end without opening Claude Desktop.
"""

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# sys.executable, not the bare string "python", so this always launches the
# exact same interpreter (and therefore the exact same virtual environment)
# that's running this script - regardless of what "python" resolves to on
# the current PATH.
SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["-m", "mcp_server.server"],
)


async def main() -> None:
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Tools this server exposes:")
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description}")
                print(f"    input schema: {json.dumps(tool.inputSchema)}")

            print("\nCalling query_health_checks(limit=3)...")
            result = await session.call_tool("query_health_checks", {"limit": 3})
            print("isError:", result.isError)
            print("structuredContent:", result.structuredContent)


if __name__ == "__main__":
    asyncio.run(main())
