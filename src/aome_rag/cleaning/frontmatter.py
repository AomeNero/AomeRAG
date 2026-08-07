"""为清洗后的 markdown 生成 YAML front-matter。"""

from __future__ import annotations

from datetime import date


def build_front_matter(title: str) -> str:
    """构建 YAML front-matter 块。

    title：来自文件名主干（传入）。
    author/description/tags：留空（规范允许）。
    date：生成日期（今天，YYYY-MM-DD）。
    """
    today = date.today().isoformat()
    return (
        "---\n"
        f'title: "{title}"\n'
        'author: ""\n'
        f'date: "{today}"\n'
        'description: ""\n'
        "tags: []\n"
        "---\n\n"
    )
