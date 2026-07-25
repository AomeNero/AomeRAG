"""s07 on-demand skill loader.

Scans src/aome_rag/skills/ for markdown skill files (directory-style with SKILL.md,
or standalone .md). Lists them in the system prompt; the model calls load_skill(name)
to inject a skill's full content into context."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aome_rag.providers.base import ToolSchema
from aome_rag.tools.base import SkillContext


class SkillLoaderSkill:
    """Provides the load_skill tool. Scans skills/ each turn (live — new .md files
    are picked up without restart)."""

    name = "load_skill"
    SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

    def _scan(self) -> list[dict[str, Any]]:
        """Scan skills/ for .md skill files. Supports:
        - Directory skills: skills/<name>/SKILL.md (name = dir name)
        - Standalone: skills/<name>.md (name = filename stem)
        Returns [{name, desc, path}]."""
        result: list[dict[str, Any]] = []
        if not self.SKILLS_DIR.is_dir():
            return result
        # directory skills: <name>/SKILL.md
        for d in sorted(self.SKILLS_DIR.iterdir()):
            if d.is_dir():
                skill_md = d / "SKILL.md"
                if skill_md.is_file():
                    result.append(
                        {"name": d.name, "desc": self._extract_desc(skill_md), "path": skill_md}
                    )
        # standalone top-level .md
        for md in sorted(self.SKILLS_DIR.glob("*.md")):
            result.append(
                {"name": md.stem, "desc": self._extract_desc(md), "path": md}
            )
        return result

    @staticmethod
    def _extract_desc(path: Path) -> str:
        """First '# heading' line, or filename stem as fallback."""
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for _ in range(10):
                    line = f.readline()
                    if not line:
                        break
                    if line.startswith("# "):
                        return line[2:].strip()
        except OSError:
            pass
        return path.stem

    @property
    def description(self) -> str:
        catalog = self._scan()
        names = ", ".join(s["name"] for s in catalog) or "(none)"
        return f"Load a skill's full content into context. Available: {names}"

    @property
    def tool_schema(self) -> ToolSchema:
        return {
            "type": "function",
            "function": {
                "name": "load_skill",
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_name": {
                            "type": "string",
                            "description": "name of the skill to load",
                        }
                    },
                    "required": ["skill_name"],
                },
            },
        }

    @property
    def system_prompt_fragment(self) -> str:
        catalog = self._scan()
        if not catalog:
            return ""
        lines = ["可用技能（调 load_skill(name) 加载完整内容到上下文）："]
        for s in catalog:
            lines.append(f"  - {s['name']}: {s['desc']}")
        return "\n".join(lines)

    async def handle(self, ctx: SkillContext, *, skill_name: str) -> str:
        catalog = self._scan()
        match = next((s for s in catalog if s["name"] == skill_name), None)
        if not match:
            available = ", ".join(s["name"] for s in catalog) or "(none)"
            return f"skill '{skill_name}' not found. Available: {available}"
        try:
            return match["path"].read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return f"failed to read skill '{skill_name}': {e}"
