"""Tests for the s07 SkillLoaderSkill."""

import pytest

from aome_rag.tools.base import SkillContext
from aome_rag.tools.skill_loader import SkillLoaderSkill

pytestmark = pytest.mark.integration  # uses real skills/pg-api/ dir


def test_scan_finds_skills() -> None:
    loader = SkillLoaderSkill()
    catalog = loader._scan()
    names = [s["name"] for s in catalog]
    assert "pg-lua-recipe" in names  # the user's PG recipe skill


def test_system_prompt_fragment_lists_skills() -> None:
    loader = SkillLoaderSkill()
    frag = loader.system_prompt_fragment
    assert "load_skill" in frag
    assert "pg-lua-recipe" in frag


def test_tool_schema_has_name() -> None:
    loader = SkillLoaderSkill()
    schema = loader.tool_schema
    assert schema["function"]["name"] == "load_skill"
    assert "pg-lua-recipe" in schema["function"]["description"]


async def test_handle_returns_content() -> None:
    loader = SkillLoaderSkill()
    result = await loader.handle(SkillContext(), skill_name="pg-lua-recipe")
    assert len(result) > 100
    assert "MIPI" in result or "LVDS" in result or "SYS" in result


async def test_handle_unknown_skill() -> None:
    loader = SkillLoaderSkill()
    result = await loader.handle(SkillContext(), skill_name="nonexistent")
    assert "not found" in result
    assert "pg-lua-recipe" in result  # lists available
