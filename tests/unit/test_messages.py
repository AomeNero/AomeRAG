from aome_rag.providers.messages import Message, TextBlock, ToolResultBlock, ToolUseBlock


def test_as_text_and_tool_uses() -> None:
    m = Message(
        role="assistant",
        blocks=[
            TextBlock(text="looking..."),
            ToolUseBlock(id="call_1", name="kb_search", arguments={"query": "x"}),
        ],
    )
    assert m.as_text() == "looking..."
    assert [tu.name for tu in m.tool_uses()] == ["kb_search"]
    assert m.tool_results() == []


def test_round_trip_via_validate() -> None:
    m = Message(
        role="tool",
        blocks=[ToolResultBlock(tool_use_id="call_1", content="hit", is_error=False)],
    )
    dumped = m.model_dump()
    rebuilt = Message.model_validate(dumped)
    assert rebuilt.role == "tool"
    assert rebuilt.tool_results()[0].content == "hit"


def test_text_helper() -> None:
    assert Message.text("user", "hi").as_text() == "hi"
