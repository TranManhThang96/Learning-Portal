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


def test_validation_error_does_not_echo_sensitive_input():
    executor = ToolExecutor()
    secret = "sk-do-not-echo-this-value"
    result = executor.run(
        "search_kb",
        {"query": secret, "top_k": 999},
        ToolContext(user_id="u1", session_id="s1", trace_id="tr1"),
    )
    assert result["status"] == "error"
    assert secret not in str(result["error"])


def test_create_ticket_requires_confirmation():
    executor = ToolExecutor()
    result = executor.run(
        "create_ticket",
        {"title": "Need help", "summary": "Please help me", "priority": "normal"},
        ToolContext(user_id="u1", session_id="s1", trace_id="tr1", idempotency_key="req1"),
    )
    assert result["status"] == "error"
    assert result["error"] == "confirmation_required"


def test_create_ticket_is_idempotent():
    executor = ToolExecutor()
    context = ToolContext(
        user_id="u1",
        session_id="s1",
        trace_id="tr1",
        idempotency_key="req1",
        confirmed_actions=frozenset({"create_ticket"}),
    )
    args = {
        "title": "Need help",
        "summary": "Please help me with billing",
        "priority": "normal",
    }
    first = executor.run("create_ticket", args, context)
    second = executor.run("create_ticket", args, context)
    assert first["ticket_id"] == second["ticket_id"]
    assert second["idempotent_replay"] is True


def test_idempotency_key_is_scoped_by_user():
    executor = ToolExecutor()
    args = {
        "title": "Need help",
        "summary": "Please help me with billing",
        "priority": "normal",
    }
    first = executor.run(
        "create_ticket",
        args,
        ToolContext(
            user_id="u1",
            session_id="s1",
            trace_id="tr1",
            idempotency_key="same-key",
            confirmed_actions=frozenset({"create_ticket"}),
        ),
    )
    second = executor.run(
        "create_ticket",
        args,
        ToolContext(
            user_id="u2",
            session_id="s2",
            trace_id="tr2",
            idempotency_key="same-key",
            confirmed_actions=frozenset({"create_ticket"}),
        ),
    )
    assert first["ticket_id"] != second["ticket_id"]
    assert second["user_id"] == "u2"


def test_idempotency_key_rejects_different_payload():
    executor = ToolExecutor()
    context = ToolContext(
        user_id="u1",
        session_id="s1",
        trace_id="tr1",
        idempotency_key="req1",
        confirmed_actions=frozenset({"create_ticket"}),
    )
    first = executor.run(
        "create_ticket",
        {"title": "Billing issue", "summary": "Duplicate charge", "priority": "normal"},
        context,
    )
    conflict = executor.run(
        "create_ticket",
        {"title": "Account issue", "summary": "Cannot sign in", "priority": "high"},
        context,
    )
    assert first["status"] == "ok"
    assert conflict["status"] == "error"
    assert conflict["error"] == "idempotency_conflict"


def test_unknown_tool_is_rejected():
    executor = ToolExecutor()
    result = executor.run("delete_user", {}, ToolContext(user_id="u1", session_id="s1", trace_id="tr1"))
    assert result["status"] == "error"
    assert result["error"] == "tool_not_allowed"
