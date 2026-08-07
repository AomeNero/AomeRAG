"""技能注册表：手动注册、按名派发、目录自动发现。"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any

import structlog

from aome_rag.providers.base import ToolSchema

from .base import Skill, SkillContext

_log = structlog.get_logger()


class SkillNotFound(KeyError):
    pass


def _is_skill_class(obj: Any) -> bool:
    """鸭子类型判断：一个具体类需有字符串 `name`、`description`、`tool_schema` 和
    `handle` 协程才算技能；排除 Protocol 本身。"""
    if not inspect.isclass(obj):
        return False
    name = getattr(obj, "name", None)
    if not isinstance(name, str) or not name:
        return False
    if obj.__module__.startswith("aome_rag.skills"):
        # 跳过本包内的基础协议/抽象类；真实技能会设置具体 name，
        # 只要定义了 name 就通过上面的判断——这里允许子类。
        pass
    return all(hasattr(obj, attr) for attr in ("description", "tool_schema", "handle"))


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        if skill.name in self._skills:
            raise ValueError(f"duplicate skill name: {skill.name}")
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def names(self) -> list[str]:
        return list(self._skills)

    def all_tool_schemas(self) -> list[ToolSchema]:
        return [s.tool_schema for s in self._skills.values()]

    def system_prompt_fragments(self) -> list[str]:
        return [s.system_prompt_fragment for s in self._skills.values() if s.system_prompt_fragment]

    def discover(self, skills_dir: str | Path) -> None:
        """从 `skills_dir` 的 .py 文件自动发现技能类（s07 注册表形态）。

        每个技能类用无参构造实例化；导入出错会记日志并跳过，重名技能跳过。"""
        path = Path(skills_dir)
        if not path.is_dir():
            return
        for mod_file in sorted(path.glob("*.py")):
            if mod_file.name.startswith("_"):
                continue
            mod_name = f"aome_rag_skill_{mod_file.stem}"
            spec = importlib.util.spec_from_file_location(mod_name, mod_file)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            try:
                spec.loader.exec_module(module)
            except Exception as e:  # noqa: BLE001
                _log.error("skill.import_failed", file=str(mod_file), error=str(e))
                continue
            for _attr, obj in inspect.getmembers(module, inspect.isclass):
                if obj.__module__ != module.__name__:
                    continue  # only classes defined in this skill file
                if not _is_skill_class(obj):
                    continue
                try:
                    self.register(obj())
                except ValueError:
                    _log.warning("skill.duplicate_skipped", name=obj.name)

    async def dispatch(self, name: str, ctx: SkillContext, **arguments: Any) -> str:
        skill = self._skills.get(name)
        if skill is None:
            raise SkillNotFound(name)
        return await skill.handle(ctx, **arguments)
