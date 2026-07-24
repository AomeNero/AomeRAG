"""Structural-first chunker: split Markdown by headings, fall back to fixed-size + overlap
for sections that exceed the limit. (~300-500 tokens approximated via a char window.)"""

from __future__ import annotations

import re


class Chunker:
    def __init__(self, target_chars: int = 1200, max_chars: int = 1600, overlap: int = 200) -> None:
        self.target = target_chars
        self.max = max_chars
        self.overlap = overlap

    def split(
        self, markdown: str, *, source_doc: str, page: int | None = None
    ) -> list[dict]:
        pieces: list[tuple[str, str]] = []  # (heading_path, text)
        for heading_path, text in self._sections(markdown):
            text = text.strip()
            if not text:
                continue
            if len(text) <= self.max:
                pieces.append((heading_path, text))
            else:
                for window in self._fixed_windows(text):
                    pieces.append((heading_path, window))
        return [
            {
                "text": text,
                "heading_path": hp,
                "chunk_index": i,
                "source_doc": source_doc,
                "page": page,
            }
            for i, (hp, text) in enumerate(pieces)
        ]

    def _sections(self, markdown: str) -> list[tuple[str, str]]:
        """Yield (heading_path, body_text) by walking Markdown headings with a level stack."""
        sections: list[tuple[str, str]] = []
        stack: list[tuple[int, str]] = []  # (level, title)
        buf: list[str] = []

        def heading_path() -> str:
            return " > ".join(title for _, title in stack)

        def flush() -> None:
            body = "".join(buf).strip()
            if body:
                sections.append((heading_path(), body))
            buf.clear()

        for line in markdown.splitlines():
            m = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
            if m:
                flush()
                level = len(m.group(1))
                title = m.group(2)
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, title))
            else:
                buf.append(line + "\n")
        flush()
        return sections

    def _fixed_windows(self, text: str) -> list[str]:
        """Greedy paragraph-accumulating windows with overlap; hard-splits any oversized result."""
        paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
        windows: list[str] = []
        cur = ""
        for p in paras:
            if not cur:
                cur = p
            elif len(cur) + len(p) + 2 <= self.target:
                cur = f"{cur}\n\n{p}"
            else:
                windows.append(cur)
                tail = cur[-self.overlap :] if self.overlap > 0 else ""
                cur = f"{tail}\n\n{p}".strip() if tail else p
        if cur.strip():
            windows.append(cur)

        final: list[str] = []
        for w in windows:
            if len(w) <= self.max:
                final.append(w)
            else:
                for i in range(0, len(w), self.target):
                    final.append(w[i : i + self.target])
        return final
