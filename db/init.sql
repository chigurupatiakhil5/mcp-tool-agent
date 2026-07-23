-- Runs automatically the first time the Postgres container starts with an
-- empty data directory (Postgres's official image executes every .sql file
-- mounted into /docker-entrypoint-initdb.d, once). If you ever need to
-- change this file after the container has already initialized once, you
-- must remove the pgdata volume (`docker compose down -v`) for it to re-run.

CREATE TABLE IF NOT EXISTS health_check (
    id SERIAL PRIMARY KEY,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id SERIAL PRIMARY KEY,
    task TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    final_answer TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id SERIAL PRIMARY KEY,
    agent_run_id INTEGER NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    iteration INTEGER NOT NULL,
    tool_name VARCHAR(100) NOT NULL,
    arguments JSONB NOT NULL,
    success BOOLEAN NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tool_calls_agent_run_id ON tool_calls(agent_run_id);
