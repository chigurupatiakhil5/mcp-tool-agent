from mcp.server.fastmcp import FastMCP

# One shared FastMCP instance. Tool modules (in mcp_server/tools/) import
# this and decorate their functions with @mcp.tool() - that decorator call
# runs at import time and registers the tool on this instance. server.py is
# the only place that actually starts the server (mcp.run()).
mcp = FastMCP("mcp-tool-agent")
