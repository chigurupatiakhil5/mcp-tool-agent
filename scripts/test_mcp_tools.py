"""Manual smoke test for the MCP server - connects to it exactly the way
Claude Desktop (and, later, our own agent) will: as a client, over stdio,
launching the server as a subprocess. Run from the project root with:

    python -m scripts.test_mcp_tools

This is not an automated test suite (that comes in v6) - it's a quick way to
prove a tool actually works end-to-end without opening Claude Desktop.
"""

import asyncio
import json

from mcp import ClientSession
from mcp.client.stdio import stdio_client

# Shared with agent/client.py (and tests/test_mcp_protocol.py) - see that
# file for why env=dict(os.environ) matters here, not just command/args.
from agent.client import SERVER_PARAMS


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

            print("\nCalling create_ticket(...)...")
            result = await session.call_tool(
                "create_ticket",
                {
                    "title": "Login page returns 500",
                    "description": "Users report a server error on /login since this morning.",
                    "priority": "high",
                },
            )
            print("isError:", result.isError)
            print("structuredContent:", result.structuredContent)

            print("\nCalling get_current_weather(city='Austin')...")
            result = await session.call_tool("get_current_weather", {"city": "Austin"})
            print("isError:", result.isError)
            print("structuredContent:", result.structuredContent)


if __name__ == "__main__":
    asyncio.run(main())
