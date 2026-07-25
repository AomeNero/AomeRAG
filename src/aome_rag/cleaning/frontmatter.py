"""YAML front-matter builder for cleaned markdown files."""

from __future__ import annotations

from datetime import date


def build_front_matter(title: str) -> str:
    """Build the YAML front-matter block.

    title: from filename stem (passed in).
    author/description/tags: empty (spec allows).
    date: generation date (today, YYYY-MM-DD).
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
