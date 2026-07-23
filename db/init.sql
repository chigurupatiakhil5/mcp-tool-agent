-- Runs automatically the first time the Postgres container starts with an
-- empty data directory (Postgres's official image executes every .sql file
-- mounted into /docker-entrypoint-initdb.d, once). If you ever need to
-- change this file after the container has already initialized once, you
-- must remove the pgdata volume (`docker compose down -v`) for it to re-run.

CREATE TABLE IF NOT EXISTS health_check (
    id SERIAL PRIMARY KEY,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
