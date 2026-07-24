import pytest

from app.database import SessionLocal


@pytest.fixture
def db():
    """A real database session against Postgres - these tests hit an actual
    database (via Docker locally, via a GitHub Actions service container in
    CI), not a mock. Tests that create rows are responsible for cleaning
    them up themselves (see test_tools.py) since this fixture doesn't wrap
    tests in a transaction rollback."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
