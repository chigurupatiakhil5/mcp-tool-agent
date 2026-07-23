from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class HealthCheck(Base):
    """Mirrors the health_check table created by db/init.sql. This table has
    no real product purpose - it exists so /health/db can prove the app can
    genuinely write to and read from Postgres, not just open a socket to it."""

    __tablename__ = "health_check"

    id = Column(Integer, primary_key=True)
    checked_at = Column(DateTime(timezone=True), server_default=func.now())


class Ticket(Base):
    """Mirrors the tickets table created by db/init.sql. Created by the
    create_ticket MCP tool (mcp_server/tools/ticket_create.py)."""

    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String(20), nullable=False, default="medium")
    status = Column(String(20), nullable=False, default="open")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
