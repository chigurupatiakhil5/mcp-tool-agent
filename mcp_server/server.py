from mcp_server.instance import mcp

# Imported for its side effect: decorating query_health_checks with
# @mcp.tool() registers it on the shared `mcp` instance above. We don't call
# anything from this module directly, which is why linters flag the import
# as "unused" - it isn't unused, it's how registration happens.
from mcp_server.tools import db_query  # noqa: F401

if __name__ == "__main__":
    # stdio transport: read/write MCP protocol messages over stdin/stdout.
    # This is what Claude Desktop expects when it launches a local server as
    # a subprocess, and what our own test script (and later, our agent) will
    # connect to the same way.
    mcp.run(transport="stdio")
