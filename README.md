# MCP Tool Agent

An MCP (Model Context Protocol) server exposing tools to Claude Desktop and a
custom Groq/LLaMA-3-powered autonomous agent, backed by FastAPI and
PostgreSQL.

**Status: v6 - Infrastructure.** Full architecture diagram and detailed docs
land in v7. This is accurate as of v6, not yet the final polished version.

## Run it

```bash
cp .env.example .env      # add your GROQ_API_KEY (free at console.groq.com)
docker compose up -d       # starts db + app
python -m scripts.apply_schema   # first time only, if db is brand new
```

Then visit:
- http://localhost:8000/ - service status
- http://localhost:8000/health - liveness check (does not touch the database)
- http://localhost:8000/health/db - proves the app can read/write PostgreSQL

## Run the agent

Fully containerized (MCP server and all - no local Python setup required):

```bash
docker compose run --rm agent
docker compose run --rm agent python -m scripts.run_agent_task "your task here"
```

## Run the tests

```bash
source .venv/bin/activate   # local virtual environment, see below
pytest -v
```

## Local development (for the MCP server / Claude Desktop integration)

Claude Desktop needs to launch the MCP server directly as a subprocess on
your machine, which means it can't be reached inside a container. For that
specific case, set up a local virtual environment (Python 3.10+ required):

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.test_mcp_tools    # smoke-test the MCP server directly
```

Full architecture docs, setup instructions, and example runs will be added
in v7.
