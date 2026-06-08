import pytest
from pydantic import ValidationError

from assistant_app.schemas import AssistantAction


def test_answer_requires_final_answer():
    with pytest.raises(ValidationError):
        AssistantAction.model_validate({"action": "answer"})


def test_call_tool_requires_tool():
    with pytest.raises(ValidationError):
        AssistantAction.model_validate({"action": "call_tool"})


def test_valid_tool_action():
    action = AssistantAction.model_validate(
        {
            "action": "call_tool",
            "tool": {"name": "search_kb", "args": {"query": "sla", "top_k": 3}},
        }
    )
    assert action.tool is not None
    assert action.tool.name == "search_kb"


def test_answer_rejects_tool_payload():
    with pytest.raises(ValidationError):
        AssistantAction.model_validate(
            {
                "action": "answer",
                "final_answer": "Done",
                "tool": {"name": "search_kb", "args": {"query": "sla"}},
            }
        )


def test_action_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        AssistantAction.model_validate(
            {
                "action": "answer",
                "final_answer": "Done",
                "unexpected": "must not be silently ignored",
            }
        )
