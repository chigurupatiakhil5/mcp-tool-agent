from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
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


class AgentRun(Base):
    """One row per call to agent.planner.run_task(). Mirrors agent_runs in
    db/init.sql."""

    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True)
    task = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="running")
    final_answer = Column(Text)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

    tool_calls = relationship("ToolCall", back_populates="agent_run", order_by="ToolCall.id")


class ToolCall(Base):
    """One row per individual tool invocation within an agent run. Mirrors
    tool_calls in db/init.sql. arguments/result are JSONB (queryable binary
    JSON), not TEXT - the point of this table is that the data inside it
    stays inspectable with real SQL, not just an opaque blob."""

    __tablename__ = "tool_calls"

    id = Column(Integer, primary_key=True)
    agent_run_id = Column(Integer, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    iteration = Column(Integer, nullable=False)
    tool_name = Column(String(100), nullable=False)
    arguments = Column(JSONB, nullable=False)
    success = Column(Boolean, nullable=False)
    result = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    agent_run = relationship("AgentRun", back_populates="tool_calls")
