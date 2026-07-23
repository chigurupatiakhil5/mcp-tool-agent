# MCP Tool Agent

An MCP (Model Context Protocol) server exposing tools to Claude Desktop and a
custom Groq/LLaMA-3-powered autonomous agent, backed by FastAPI and
PostgreSQL.

**Status: v0 - Foundation.** FastAPI + PostgreSQL running in Docker Compose.
No MCP or agent functionality yet - that starts in v1.

## Run it

```bash
cp .env.example .env
docker compose up --build
```

Then visit:
- http://localhost:8000/ - service status
- http://localhost:8000/health - liveness check (does not touch the database)
- http://localhost:8000/health/db - proves the app can read/write PostgreSQL
  (each call inserts a row and returns the running total)

Full architecture docs, setup instructions, and example runs will be added
as the project builds out through v7.
