import pytest

from aome_rag.providers.base import Finish, TextDelta, ToolCallDelta
from aome_rag.providers.errors import ToolCallParseError
from aome_rag.providers.messages import Message, TextBlock, ToolResultBlock, ToolUseBlock
from aome_rag.providers.openai_compat import (
    messages_to_openai,
    parse_stream_chunk,
    parse_tool_arguments,
    response_to_llm_response,
)

PLAIN = {
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
}

TOOL = {
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "kb_search",
                            "arguments": '{"query": "foo", "top_k": 3}',
                        },
                    }
                ],
            },
            "finish_reason": "tool_calls",
        }
    ],
    "usage": {},
}

BAD = {
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "kb_search", "arguments": "not json{"},
                    }
                ],
            },
            "finish_reason": "tool_calls",
        }
    ]
}

CHUNKS = [
    {"choices": [{"index": 0, "delta": {"role": "assistant", "content": "Hi"}, "finish_reason": None}]},
    {
        "choices": [
            {
                "index": 0,
                "delta": {
                    "tool_calls": [
                        {"index": 0, "id": "call_1", "function": {"name": "kb_search", "arguments": '{"q":'}}
                    ]
                },
                "finish_reason": None,
            }
        ]
    },
    {
        "choices": [
            {"index": 0, "delta": {"tool_calls": [{"index": 0, "function": {"arguments": '"x"}'}}]}, "finish_reason": None}
        ]
    },
    {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
]


def test_response_plain() -> None:
    r = response_to_llm_response(PLAIN)
    assert r.finish_reason == "stop"
    assert r.message.as_text() == "hello"
    assert r.usage is not None and r.usage.input_tokens == 5


def test_response_tool_calls_normalized() -> None:
    r = response_to_llm_response(TOOL)
    assert r.finish_reason == "tool_use"  # OpenAI "tool_calls" -> internal "tool_use"
    tus = r.message.tool_uses()
    assert len(tus) == 1 and tus[0].name == "kb_search"
    assert tus[0].arguments == {"query": "foo", "top_k": 3}


def test_response_bad_arguments_raises() -> None:
    with pytest.raises(ToolCallParseError):
        response_to_llm_response(BAD)


def test_parse_tool_arguments() -> None:
    assert parse_tool_arguments('{"a": 1}') == {"a": 1}
    assert parse_tool_arguments("") == {}
    with pytest.raises(ToolCallParseError):
        parse_tool_arguments("nope")
    with pytest.raises(ToolCallParseError):
        parse_tool_arguments("[1, 2]")  # not an object


def test_messages_to_openai() -> None:
    msgs = [
        Message.text("system", "be helpful"),
        Message.text("user", "hi"),
        Message(
            role="assistant",
            blocks=[ToolUseBlock(id="call_1", name="kb_search", arguments={"query": "x"})],
        ),
        Message(role="tool", blocks=[ToolResultBlock(tool_use_id="call_1", content="hit")]),
    ]
    wire = messages_to_openai(msgs)
    assert wire[0] == {"role": "system", "content": "be helpful"}
    assert wire[1] == {"role": "user", "content": "hi"}
    assert wire[2]["role"] == "assistant"
    assert wire[2]["tool_calls"][0]["id"] == "call_1"
    assert wire[2]["tool_calls"][0]["function"]["arguments"] == '{"query": "x"}'
    assert wire[3] == {"role": "tool", "tool_call_id": "call_1", "content": "hit"}


def test_messages_to_openai_fans_out_embedded_tool_result() -> None:
    # clarify persists its result INSIDE the assistant message; the wire format must still
    # pair every tool_calls with a trailing tool message or OpenAI-compatible APIs 400.
    msgs = [
        Message.text("user", "328产品"),
        Message(
            role="assistant",
            blocks=[
                TextBlock(text="选A/B/C?"),
                ToolUseBlock(id="call_c", name="clarify", arguments={"question": "x"}),
                ToolResultBlock(tool_use_id="call_c", content="", is_error=False),
            ],
        ),
        Message.text("user", "A 电源规格"),
    ]
    wire = messages_to_openai(msgs)
    assert wire[1]["role"] == "assistant"
    assert wire[1]["tool_calls"][0]["id"] == "call_c"
    # embedded result must be emitted as a trailing tool message (between assistant and user)
    assert wire[2] == {"role": "tool", "tool_call_id": "call_c", "content": ""}
    assert wire[3] == {"role": "user", "content": "A 电源规格"}


def test_parse_stream_chunk() -> None:
    d0 = parse_stream_chunk(CHUNKS[0])
    assert isinstance(d0[0], TextDelta) and d0[0].text == "Hi"

    d1 = parse_stream_chunk(CHUNKS[1])
    assert isinstance(d1[0], ToolCallDelta)
    assert d1[0].index == 0 and d1[0].name == "kb_search" and d1[0].arguments_chunk == '{"q":'

    d3 = parse_stream_chunk(CHUNKS[3])
    assert isinstance(d3[0], Finish) and d3[0].finish_reason == "tool_use"
