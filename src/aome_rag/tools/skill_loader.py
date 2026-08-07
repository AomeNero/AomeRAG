"""按需技能加载器：扫描包内 skills/ 的 .md 技能文件，命中后把全文注入上下文。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aome_rag.providers.base import ToolSchema
from aome_rag.tools.base import SkillContext


class SkillLoaderSkill:
    """load_skill 工具。每轮实时扫描 skills/（新增 .md 文件无需重启即生效）。"""

    name = "load_skill"
    SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

    def _scan(self) -> list[dict[str, Any]]:
        """扫描 skills/ 下的 .md 技能文件，支持：
        - 目录式：skills/<name>/SKILL.md（name = 目录名）
        - 独立式：skills/<name>.md（name = 文件名）
        返回 [{name, desc, path}]。desc 取自 frontmatter 的 description（见 _extract_desc）。"""
        result: list[dict[str, Any]] = []
        if not self.SKILLS_DIR.is_dir():
            return result
        # 目录式技能：<name>/SKILL.md
        for d in sorted(self.SKILLS_DIR.iterdir()):
            if d.is_dir():
                skill_md = d / "SKILL.md"
                if skill_md.is_file():
                    result.append(
                        {"name": d.name, "desc": self._extract_desc(skill_md), "path": skill_md}
                    )
        # 独立顶层 .md
        for md in sorted(self.SKILLS_DIR.glob("*.md")):
            result.append(
                {"name": md.stem, "desc": self._extract_desc(md), "path": md}
            )
        return result

    @staticmethod
    def _extract_desc(path: Path) -> str:
        """提取 YAML frontmatter 的 `description:` 字段（即触发条件，供 agent 判断是否命中）。

        这是"描述路由"的关键：目录里展示的是一段能说明何时该用本技能的触发描述，
        而不是笼统的标题。无 frontmatter 时回退到首个 '# 标题'，再退到文件名。"""
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return Path(path).stem
        lines = text.splitlines()
        if lines and lines[0].strip() == "---":
            for line in lines[1:]:
                stripped = line.strip()
                if stripped == "---":
                    break
                if stripped.startswith("description:"):
                    return stripped[len("description:"):].strip()
        for line in lines[:12]:
            if line.startswith("# "):
                return line[2:].strip()
        return Path(path).stem

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
