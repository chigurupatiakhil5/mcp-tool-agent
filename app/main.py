from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import HealthCheck

app = FastAPI(title="MCP Tool Agent")


@app.get("/")
def root():
    return {"status": "ok", "service": "mcp-tool-agent"}


@app.get("/health")
def health():
    """Liveness check - proves the FastAPI process itself is up. Does not
    touch the database, so it stays fast and can't fail because of a DB
    problem. That's a separate, deliberate check below."""
    return {"status": "healthy"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    """Readiness check - proves the app can actually read and write
    Postgres, not just hold an open connection. Each call inserts a new row
    and returns the running total, so calling this endpoint twice in a row
    should show total_checks_recorded increase by one - a real, visible
    signal that this isn't a canned response."""
    check = HealthCheck()
    db.add(check)
    db.commit()
    db.refresh(check)

    total = db.query(HealthCheck).count()

    return {
        "status": "healthy",
        "inserted_id": check.id,
        "checked_at": check.checked_at,
        "total_checks_recorded": total,
    }
