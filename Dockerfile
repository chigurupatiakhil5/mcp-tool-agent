FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# One image serves both the app and agent services (see docker-compose.yml)
# - the agent launches the MCP server as its own subprocess (agent/client.py),
# so it needs mcp_server/ in the same image, not a separate one. There's no
# standalone MCP server container: a stdio-transport server has no
# persistent stdin to read from without a client attached to it directly.
COPY app ./app
COPY mcp_server ./mcp_server
COPY agent ./agent
COPY scripts ./scripts
COPY db ./db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
