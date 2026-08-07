"""系统提示词装配：基础提示词 + 各技能提示片段，运行时拼装。"""

from __future__ import annotations

from .prompts import load_base_prompt


def assemble_system_prompt(skill_fragments: list[str]) -> str:
    parts = [load_base_prompt()]
    parts.extend(f for f in skill_fragments if f)
    return "\n\n".join(parts)
