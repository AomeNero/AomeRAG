"""Runtime system-prompt assembly: base + per-skill fragments."""

from __future__ import annotations

from .prompts import BASE_SYSTEM_PROMPT


def assemble_system_prompt(skill_fragments: list[str]) -> str:
    parts = [BASE_SYSTEM_PROMPT]
    parts.extend(f for f in skill_fragments if f)
    return "\n\n".join(parts)
