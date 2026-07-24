"""Applies db/init.sql against whatever Postgres the current environment's
config points at (app/config.py's Settings - reads .env locally, or real
environment variables in CI/Docker).

Every statement in init.sql uses "IF NOT EXISTS", so this is safe to run
against a brand new database (first-time setup) or one that already has the
schema (a clean no-op). This is different from Postgres's own automatic
behavior for files in /docker-entrypoint-initdb.d/, which only ever run
once, on a container's first boot with an empty data directory (see v0) -
this script can be re-run any time, which is exactly what CI needs against
a freshly-provisioned, empty service container on every run.

    python -m scripts.apply_schema
"""

from pathlib import Path

from sqlalchemy import text

from app.database import engine

INIT_SQL_PATH = Path(__file__).resolve().parent.parent / "db" / "init.sql"


def main() -> None:
    sql = INIT_SQL_PATH.read_text()
    with engine.begin() as connection:
        connection.execute(text(sql))
    print(f"Applied {INIT_SQL_PATH}")


if __name__ == "__main__":
    main()
