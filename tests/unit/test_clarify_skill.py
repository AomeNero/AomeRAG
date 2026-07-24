import pytest

from aome_rag.agent.events import ClarifyEvent, FinalEvent
from aome_rag.agent.loop import AgentLoop
from aome_rag.providers.base import Finish, ToolCallDelta
from aome_rag.skills.base import EndTurn, SkillContext
from aome_rag.skills.clarify import ClarifySkill
from aome_rag.skills.registry import SkillRegistry

from tests.fakes import FakeProvider


async def test_clarify_handle_emits_and_ends_turn() -> None:
    skill = ClarifySkill()
    ctx = SkillContext()
    with pytest.raises(EndTurn):
        await skill.handle(ctx, question="which version?")
    assert ctx.pending and isinstance(ctx.pending[0], ClarifyEvent)
    assert ctx.pending[0].question == "which version?"


async def test_loop_clarify_ends_turn_without_second_llm_call() -> None:
    provider = FakeProvider()
    provider.enqueue(
        [
            ToolCallDelta(
                index=0, id="call_1", name="clarify", arguments_chunk='{"question": "which?"}'
            ),
            Finish(finish_reason="tool_calls"),
        ]
    )
    reg = SkillRegistry()
    reg.register(ClarifySkill())
    loop = AgentLoop(provider, reg, max_iterations=4)

    events = [e async for e in loop.run([], "do the thing")]
    types = [type(e).__name__ for e in events]

    assert "ClarifyEvent" in types
    assert types[-1] == "FinalEvent"
    # the loop must not have tried a second provider call (script had only one entry)
    assert provider._script == []
