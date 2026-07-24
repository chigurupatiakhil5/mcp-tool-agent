"""Integration tests: spin up the real MCP server as a subprocess and talk
to it over stdio, exactly like Claude Desktop and our agent do. This is the
only place schema generation and structuredContent behavior (see v2) are
actually exercised - test_tools.py calls the underlying functions directly
and never touches the MCP protocol layer at all.

Deliberately not covered here: the Groq-powered agent loop (agent/planner.py).
Testing that would require a GROQ_API_KEY as a CI secret and real network
calls to Groq on every push - a real cost/flakiness tradeoff this project
doesn't take on for v6. These tests cover everything the tools themselves
promise, independent of any particular LLM's tool-calling decisions.
"""

from mcp import ClientSession
from mcp.client.stdio import stdio_client

from agent.client import SERVER_PARAMS
from app.models import Ticket


async def test_server_exposes_three_tools():
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            assert names == {"query_health_checks", "create_ticket", "get_current_weather"}


async def test_create_ticket_tool_returns_structured_success(db):
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "create_ticket",
                {"title": "protocol test ticket", "description": "created via MCP client"},
            )

    assert result.isError is False
    data = result.structuredContent["result"]
    assert data["title"] == "protocol test ticket"

    row = db.query(Ticket).filter(Ticket.id == data["id"]).first()
    assert row is not None
    db.delete(row)
    db.commit()


async def test_create_ticket_tool_reports_validation_failure_without_protocol_error():
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("create_ticket", {"title": "", "description": "x"})

    # A business-logic failure (empty title) is not a protocol error - the
    # call succeeded, it just reported that the input was invalid. See v2.
    assert result.isError is False
    assert result.structuredContent["result"]["error"] == "title cannot be empty"


async def test_unknown_tool_name_reports_protocol_error():
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("not_a_real_tool", {})

    # Verified in v4: this is isError=True, never a raised exception.
    assert result.isError is True


async def test_weather_tool_returns_real_data_for_a_known_city():
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("get_current_weather", {"city": "Austin"})

    assert result.isError is False
    data = result.structuredContent["result"]
    assert "error" not in data
    assert data["city"] == "Austin"
    assert isinstance(data["temperature_c"], (int, float))
