from mcp_server.instance import mcp

# Imported for their side effects: each decorates a function with
# @mcp.tool(), registering it on the shared `mcp` instance above. We don't
# call anything from these modules directly, which is why linters flag the
# imports as "unused" - they aren't, this is how registration happens.
from mcp_server.tools import (
    db_query,  # noqa: F401
    external_api,  # noqa: F401
    ticket_create,  # noqa: F401
)

if __name__ == "__main__":
    # stdio transport: read/write MCP protocol messages over stdin/stdout.
    # This is what Claude Desktop expects when it launches a local server as
    # a subprocess, and what our own test script (and later, our agent) will
    # connect to the same way.
    mcp.run(transport="stdio")
