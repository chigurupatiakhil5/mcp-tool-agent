"""Unit-level tests: call the MCP tool functions directly, as plain Python
functions, bypassing the MCP protocol layer entirely. This tests the actual
business logic (validation, database reads/writes) at the fastest, most
direct level. tests/test_mcp_protocol.py separately tests the same tools
*through* the real MCP protocol, which is a genuinely different thing to
verify - schema generation and structuredContent behavior only show up at
that layer, not here.
"""

from app.models import HealthCheck, Ticket
from mcp_server.tools.db_query import query_health_checks
from mcp_server.tools.ticket_create import create_ticket


def test_create_ticket_rejects_empty_title():
    result = create_ticket(title="   ", description="valid description")
    assert result == {"error": "title cannot be empty"}


def test_create_ticket_rejects_empty_description():
    result = create_ticket(title="valid title", description="   ")
    assert result == {"error": "description cannot be empty"}


def test_create_ticket_creates_a_real_row(db):
    result = create_ticket(title="pytest ticket", description="created by automated test", priority="low")

    assert "error" not in result
    assert result["title"] == "pytest ticket"
    assert result["priority"] == "low"
    assert result["status"] == "open"

    row = db.query(Ticket).filter(Ticket.id == result["id"]).first()
    assert row is not None
    assert row.title == "pytest ticket"

    db.delete(row)
    db.commit()


def test_query_health_checks_returns_recent_rows(db):
    check = HealthCheck()
    db.add(check)
    db.commit()
    db.refresh(check)

    try:
        results = query_health_checks(limit=5)
        assert any(r["id"] == check.id for r in results)
    finally:
        db.delete(check)
        db.commit()
