from typing import Literal

from typing_extensions import TypedDict

from app.database import SessionLocal
from app.models import Ticket
from mcp_server.instance import mcp
from mcp_server.types import ToolError


class TicketResult(TypedDict):
    id: int
    title: str
    priority: str
    status: str
    created_at: str


@mcp.tool()
def create_ticket(
    title: str,
    description: str,
    priority: Literal["low", "medium", "high", "urgent"] = "medium",
) -> TicketResult | ToolError:
    """Create a support ticket.

    Args:
        title: Short summary of the issue.
        description: Full details of the issue.
        priority: One of low, medium, high, urgent. Defaults to medium.
    """
    title = title.strip()
    description = description.strip()

    if not title:
        return {"error": "title cannot be empty"}
    if not description:
        return {"error": "description cannot be empty"}

    db = SessionLocal()
    try:
        ticket = Ticket(title=title, description=description, priority=priority)
        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        return {
            "id": ticket.id,
            "title": ticket.title,
            "priority": ticket.priority,
            "status": ticket.status,
            "created_at": ticket.created_at.isoformat(),
        }
    finally:
        db.close()
