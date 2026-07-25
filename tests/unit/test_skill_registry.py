import textwrap
from pathlib import Path

from aome_rag.tools.base import SkillContext
from aome_rag.tools.registry import SkillRegistry

_STUB = textwrap.dedent(
    """
    class HelloSkill:
        name = "hello"
        description = "say hello"
        tool_schema = {"type": "function", "function": {"name": "hello", "description": "d",
                       "parameters": {"type": "object", "properties": {}}}}
        system_prompt_fragment = None

        async def handle(self, ctx, **arguments):
            return "hi"
    """
)

_STUB_2 = textwrap.dedent(
    """
    class WorldSkill:
        name = "world"
        description = "say world"
        tool_schema = {"type": "function", "function": {"name": "world", "description": "d",
                       "parameters": {"type": "object", "properties": {}}}}
        system_prompt_fragment = None

        async def handle(self, ctx, **arguments):
            return "world"
    """
)


def test_discover_loads_skill_files(tmp_path: Path) -> None:
    (tmp_path / "hello.py").write_text(_STUB, encoding="utf-8")
    reg = SkillRegistry()
    reg.discover(tmp_path)
    assert reg.names() == ["hello"]
    assert reg.get("hello").tool_schema["function"]["name"] == "hello"


def test_discover_picks_up_added_file_with_zero_loop_change(tmp_path: Path) -> None:
    (tmp_path / "hello.py").write_text(_STUB, encoding="utf-8")
    reg = SkillRegistry()
    reg.discover(tmp_path)
    assert reg.names() == ["hello"]
    # add a second skill file; re-discover (the registry/loop code is unchanged)
    (tmp_path / "world.py").write_text(_STUB_2, encoding="utf-8")
    reg.discover(tmp_path)
    assert set(reg.names()) == {"hello", "world"}


async def test_dispatch_discovered_skill(tmp_path: Path) -> None:
    (tmp_path / "hello.py").write_text(_STUB, encoding="utf-8")
    reg = SkillRegistry()
    reg.discover(tmp_path)
    result = await reg.dispatch("hello", SkillContext())
    assert result == "hi"


def test_discover_skips_bad_file(tmp_path: Path) -> None:
    (tmp_path / "good.py").write_text(_STUB, encoding="utf-8")
    (tmp_path / "bad.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    reg = SkillRegistry()
    reg.discover(tmp_path)  # must not raise
    assert reg.names() == ["hello"]
