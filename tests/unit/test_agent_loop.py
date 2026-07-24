import pytest

from aome_rag.agent.events import ErrorEvent, FinalEvent, TokenEvent, ToolResultEvent, ToolStartEvent
from aome_rag.agent.loop import AgentLoop
from aome_rag.providers.base import Finish, TextDelta, ToolCallDelta, ToolSchema
from aome_rag.providers.messages import Message
from aome_rag.skills.base import Skill, SkillContext
from aome_rag.skills.registry import SkillRegistry

from tests.fakes import FakeProvider


class StubSkill:
    def __init__(self, name: str = "stub", retval: str = "stub-result") -> None:
        self.name = name
        self.description = "stub skill"
        self.tool_schema: ToolSchema = {
            "type": "function",
            "function": {
                "name": name,
                "description": "stub",
                "parameters": {"type": "object", "properties": {"x": {"type": "string"}}},
            },
        }
        self.system_prompt_fragment = None
        self.retval = retval
        self.seen_args: list[dict] = []

    async def handle(self, ctx: SkillContext, **arguments) -> str:
        self.seen_args.append(arguments)
        return self.retval


def _tool_use_stream(name="stub", args='{"x": "1"}'):
    return [
        ToolCallDelta(index=0, id="call_1", name=name, arguments_chunk=args),
        Finish(finish_reason="tool_calls"),
    ]


def _final_stream(text="done"):
    return [TextDelta(text=text), Finish(finish_reason="stop")]


def _types(events):
    return [type(e).__name__ for e in events]


async def test_loop_tool_then_final() -> None:
    provider = FakeProvider()
    provider.enqueue(_tool_use_stream())
    provider.enqueue(_final_stream("the answer"))
    skill = StubSkill()
    reg = SkillRegistry()
    reg.register(skill)
    loop = AgentLoop(provider, reg, max_iterations=4)

    history: list[Message] = []
    events = [e async for e in loop.run(history, "hi")]

    assert _types(events) == ["ToolStartEvent", "ToolResultEvent", "TokenEvent", "FinalEvent"]
    assert isinstance(events[0], ToolStartEvent) and events[0].name == "stub"
    assert isinstance(events[1], ToolResultEvent) and events[1].content == "stub-result"
    assert isinstance(events[2], TokenEvent) and events[2].text == "the answer"
    # history: user, assistant(tool_use), tool(result), assistant(text)
    assert [m.role for m in history] == ["user", "assistant", "tool", "assistant"]
    assert skill.seen_args == [{"x": "1"}]


async def test_loop_max_iter_errors() -> None:
    provider = FakeProvider()
    for _ in range(3):
        provider.enqueue(_tool_use_stream())
    reg = SkillRegistry()
    reg.register(StubSkill())
    loop = AgentLoop(provider, reg, max_iterations=2)

    events = [e async for e in loop.run([], "hi")]
    assert any(isinstance(e, ErrorEvent) and e.code == "max_iter" for e in events)
    assert not any(isinstance(e, FinalEvent) for e in events)


async def test_loop_bad_arguments_yielded_as_error() -> None:
    provider = FakeProvider()
    provider.enqueue(_tool_use_stream(args="not json{"))
    provider.enqueue(_final_stream("ok"))
    skill = StubSkill()
    reg = SkillRegistry()
    reg.register(skill)
    loop = AgentLoop(provider, reg, max_iterations=3)

    events = [e async for e in loop.run([], "hi")]
    tr = next(e for e in events if isinstance(e, ToolResultEvent))
    assert tr.is_error is True
    assert skill.seen_args == []  # skill was NOT called for the parse-failed tool


async def test_loop_skill_exception_becomes_error_result() -> None:
    class BoomSkill(StubSkill):
        async def handle(self, ctx: SkillContext, **arguments) -> str:
            raise RuntimeError("boom")

    provider = FakeProvider()
    provider.enqueue(_tool_use_stream())
    provider.enqueue(_final_stream("ok"))
    reg = SkillRegistry()
    reg.register(BoomSkill())
    loop = AgentLoop(provider, reg, max_iterations=3)

    events = [e async for e in loop.run([], "hi")]
    tr = next(e for e in events if isinstance(e, ToolResultEvent))
    assert tr.is_error is True and "boom" in tr.content


def test_stub_skill_satisfies_protocol() -> None:
    assert isinstance(StubSkill(), Skill)
