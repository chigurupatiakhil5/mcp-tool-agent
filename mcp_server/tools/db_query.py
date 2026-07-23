from sqlalchemy import desc

from app.database import SessionLocal
from app.models import HealthCheck
from mcp_server.instance import mcp


@mcp.tool()
def query_health_checks(limit: int = 5) -> list[dict]:
    """Query the most recent health check records from the database.

    Args:
        limit: Maximum number of records to return (default 5).
    """
    db = SessionLocal()
    try:
        rows = (
            db.query(HealthCheck)
            .order_by(desc(HealthCheck.checked_at))
            .limit(limit)
            .all()
        )
        return [
            {"id": row.id, "checked_at": row.checked_at.isoformat()}
            for row in rows
        ]
    finally:
        db.close()
