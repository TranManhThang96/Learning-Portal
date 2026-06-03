from assistant_app.schemas import ToolContext
from assistant_app.tools import ToolExecutor


def test_search_kb_limits_top_k():
    executor = ToolExecutor()
    result = executor.run(
        "search_kb",
        {"query": "SLA Pro support refund security", "top_k": 2},
        ToolContext(user_id="u1", session_id="s1", trace_id="tr1"),
    )
    assert result["status"] == "ok"
    assert len(result["items"]) <= 2


def test_create_ticket_requires_confirmation():
    executor = ToolExecutor()
    result = executor.run(
        "create_ticket",
        {"title": "Need help", "summary": "Please help me", "priority": "normal", "user_confirmed": False},
        ToolContext(user_id="u1", session_id="s1", trace_id="tr1", idempotency_key="req1"),
    )
    assert result["status"] == "error"
    assert result["error"] == "confirmation_required"


def test_create_ticket_is_idempotent():
    executor = ToolExecutor()
    context = ToolContext(user_id="u1", session_id="s1", trace_id="tr1", idempotency_key="req1")
    args = {
        "title": "Need help",
        "summary": "Please help me with billing",
        "priority": "normal",
        "user_confirmed": True,
    }
    first = executor.run("create_ticket", args, context)
    second = executor.run("create_ticket", args, context)
    assert first["ticket_id"] == second["ticket_id"]
    assert second["idempotent_replay"] is True


def test_unknown_tool_is_rejected():
    executor = ToolExecutor()
    result = executor.run("delete_user", {}, ToolContext(user_id="u1", session_id="s1", trace_id="tr1"))
    assert result["status"] == "error"
    assert result["error"] == "tool_not_allowed"
