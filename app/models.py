from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.sql import func

from app.database import Base


class HealthCheck(Base):
    """Mirrors the health_check table created by db/init.sql. This table has
    no real product purpose - it exists so /health/db can prove the app can
    genuinely write to and read from Postgres, not just open a socket to it."""

    __tablename__ = "health_check"

    id = Column(Integer, primary_key=True)
    checked_at = Column(DateTime(timezone=True), server_default=func.now())
