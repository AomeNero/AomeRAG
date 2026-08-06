"""Built-in workspace tools: read / write / edit / bash.

All four operate inside a single workspace directory (default `./workspace`,
sibling of `data/`). Path arguments are relative to the workspace root; every
access is validated so the resolved path cannot escape the workspace. bash runs
PowerShell with the workspace as CWD. Every call is written to the audit log
(tools.log) with the calling user + session + command/path.
"""

from __future__ import annotations

import asyncio
import base64
import re
import subprocess
from pathlib import Path
from typing import Any

import structlog

from aome_rag.providers.base import ToolSchema
from aome_rag.tools.base import SkillContext

_log = structlog.get_logger()

MAX_READ_BYTES = 100 * 1024  # 100 KB — cap on the RETURNED content (a section read returns less)
MAX_READ_FILE_BYTES = 5 * 1024 * 1024  # 5 MB — hard cap on reading a file into memory
MAX_WRITE_BYTES = 1024 * 1024  # 1 MB
BASH_TIMEOUT_S = 30
BASH_OUTPUT_LIMIT = 4000


def _resolve_workspace_path(workspace: Path, rel: str) -> Path:
    """Validate a workspace-relative path and return the resolved absolute Path.

    Raises ValueError for absolute paths, empty strings, or anything that
    resolves outside the workspace (e.g. `..` traversal)."""
    p = Path(rel)
    if not rel or p.is_absolute() or p.anchor:
        raise ValueError(f"invalid workspace path: {rel!r}")
    root = workspace.resolve()
    resolved = (workspace / p).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"path escapes workspace: {rel!r}")
    return resolved


def _audit(ctx: SkillContext, event: str, **kw: Any) -> None:
    user_id = getattr(ctx.user, "id", None)
    _log.info(event, user=user_id, session_id=ctx.session_id or None, **kw)


def _split_path_heading(path: str) -> tuple[str, str | None]:
    """Split `file#heading` into (file, heading). `#` with empty heading → "" (TOC);
    no `#` at all → None (whole file)."""
    if "#" in path:
        file_part, heading = path.rsplit("#", 1)
        return file_part, heading
    return path, None


def _extract_section(text: str, heading: str) -> str | None:
    """Return the block from the matching heading to the next same-or-higher
    level heading. Exact `## name` match first, then a case-insensitive
    contains-match (for fuzzy model names). Empty heading returns the TOC of all
    level-1/2 headings. Returns None when the heading is not found."""
    lines = text.splitlines()
    if not heading:
        toc = [ln.strip() for ln in lines if re.match(r"^#{1,2}\s", ln.strip())]
        return "\n".join(toc) if toc else "(no headings)"
    idx: int | None = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s == f"## {heading}" or s == f"# {heading}":
            idx = i
            break
    if idx is None:
        low = heading.lower()
        for i, ln in enumerate(lines):
            s = ln.strip()
            if re.match(r"^#{1,2}\s", s) and low in s.lower():
                idx = i
                break
    if idx is None:
        return None
    out = [lines[idx]]
    for ln in lines[idx + 1:]:
        s = ln.strip()
        if re.match(r"^#{1,2}\s", s):
            break
        out.append(ln)
    return "\n".join(out)


class ReadTool:
    name = "read"
    description = "Read a UTF-8 text file inside the workspace or a skill reference (max 100KB)."
    system_prompt_fragment = (
        "Tools `read`/`write`/`edit`/`bash` operate inside the workspace directory "
        "(`./workspace`). `read` can ALSO read a skill's files (read-only) via "
        "`@skill/<name>/<subdir>/<file>` (e.g. references/, assets/), optionally `#<heading>` "
        "for just that section, or `#` for the table of contents. `write`/`edit`/`bash` stay "
        "workspace-only."
    )

    tool_schema: ToolSchema = {
        "type": "function",
        "function": {
            "name": "read",
            "description": "Read a UTF-8 text file inside the workspace (max 100KB), or a skill "
            "file via @skill/<name>/<subdir>/<file> (read-only, e.g. references/, assets/). "
            "Append #<heading> to read just that section, or # for the table of contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "workspace-relative path, or @skill/<name>/<subdir>/<file> "
                            "with optional #<heading>"
                        ),
                    }
                },
                "required": ["path"],
            },
        },
    }

    def __init__(self, workspace_dir: str | Path, skills_dir: str | Path | None = None) -> None:
        self._workspace = Path(workspace_dir)
        self._skills_dir = (
            Path(skills_dir)
            if skills_dir is not None
            else Path(__file__).resolve().parent.parent / "skills"
        )

    def _resolve_read_path(self, rel: str) -> Path:
        """Resolve a read path: either a workspace-relative path or an
        `@skill/<name>/<sub>/<file>` path confined to that skill's directory
        (references/, assets/, ... — read-only package content)."""
        if rel.startswith("@skill/"):
            parts = rel[len("@skill/"):].split("/")
            if len(parts) < 2:
                raise ValueError(f"invalid skill reference path: {rel!r}")
            name = parts[0]
            if not name or name in (".", "..") or "/" in name or "\\" in name:
                raise ValueError(f"invalid skill reference path: {rel!r}")
            root = (self._skills_dir / name).resolve()
            file_rel = "/".join(parts[1:])
            p = Path(file_rel)
            if not file_rel or p.is_absolute() or p.anchor:
                raise ValueError(f"invalid skill reference path: {rel!r}")
            resolved = (root / p).resolve()
            if not resolved.is_relative_to(root):
                raise ValueError(f"path escapes skill directory: {rel!r}")
            return resolved
        return _resolve_workspace_path(self._workspace, rel)

    async def handle(self, ctx: SkillContext, *, path: str) -> str:
        file_part, heading = _split_path_heading(path)
        try:
            target = self._resolve_read_path(file_part)
        except ValueError as e:
            return str(e)
        if not target.is_file():
            return f"file not found: {path}"
        size = target.stat().st_size
        if size > MAX_READ_FILE_BYTES:
            return f"file too large ({size} bytes)"
        data = await asyncio.to_thread(target.read_bytes)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return f"{path} is not a UTF-8 text file"
        if heading is not None:
            section = _extract_section(text, heading)
            if section is None:
                return f"heading not found: {heading}"
            text = section
        out_bytes = len(text.encode("utf-8"))
        if out_bytes > MAX_READ_BYTES:
            return f"content too large ({out_bytes} bytes > {MAX_READ_BYTES})"
        _audit(ctx, "tool.read", path=path, size=out_bytes)
        return text


class WriteTool:
    name = "write"
    description = "Write a text file inside the workspace (creates parent dirs, overwrites)."
    system_prompt_fragment = None

    tool_schema: ToolSchema = {
        "type": "function",
        "function": {
            "name": "write",
            "description": "Write a text file inside the workspace (creates parent dirs, "
            "overwrites existing; content up to 1MB).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "workspace-relative path, e.g. 'report.md'",
                    },
                    "content": {"type": "string", "description": "full file content"},
                },
                "required": ["path", "content"],
            },
        },
    }

    def __init__(self, workspace_dir: str | Path) -> None:
        self._workspace = Path(workspace_dir)

    async def handle(self, ctx: SkillContext, *, path: str, content: str) -> str:
        try:
            target = _resolve_workspace_path(self._workspace, path)
        except ValueError as e:
            return str(e)
        raw = content.encode("utf-8")
        if len(raw) > MAX_WRITE_BYTES:
            return f"content too large ({len(raw)} bytes > {MAX_WRITE_BYTES})"
        await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(target.write_bytes, raw)
        _audit(ctx, "tool.write", path=path, size=len(raw))
        return f"wrote {len(raw)} bytes to {path}"


class EditTool:
    name = "edit"
    description = "Replace an exact substring in a workspace file (all occurrences)."
    system_prompt_fragment = None

    tool_schema: ToolSchema = {
        "type": "function",
        "function": {
            "name": "edit",
            "description": "Replace an exact substring in a workspace file. Replaces ALL "
            "occurrences. Errors if the find-string is not present verbatim — retry with an "
            "exact snippet from the file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "workspace-relative path",
                    },
                    "find": {
                        "type": "string",
                        "description": "exact substring to replace (must appear in the file)",
                    },
                    "replace": {"type": "string", "description": "replacement text"},
                },
                "required": ["path", "find", "replace"],
            },
        },
    }

    def __init__(self, workspace_dir: str | Path) -> None:
        self._workspace = Path(workspace_dir)

    async def handle(self, ctx: SkillContext, *, path: str, find: str, replace: str) -> str:
        try:
            target = _resolve_workspace_path(self._workspace, path)
        except ValueError as e:
            return str(e)
        if not target.is_file():
            return f"file not found: {path}"
        original = await asyncio.to_thread(target.read_text, encoding="utf-8")
        if find not in original:
            return f"not found in {path}: {find[:80]!r}"
        count = original.count(find)
        updated = original.replace(find, replace)
        await asyncio.to_thread(target.write_text, updated, encoding="utf-8")
        _audit(ctx, "tool.edit", path=path, replaced=count, find_len=len(find))
        return f"replaced {count} occurrence(s) in {path}"


class BashTool:
    name = "bash"
    description = "Run a PowerShell command on the server (CWD = workspace, 30s timeout)."
    system_prompt_fragment = None

    tool_schema: ToolSchema = {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a PowerShell command on the server. Working directory is the "
            "workspace. Output limited to 4000 chars, 30s timeout. Use for file inspection or "
            "workspace automation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "PowerShell command to execute"},
                },
                "required": ["command"],
            },
        },
    }

    def __init__(self, workspace_dir: str | Path) -> None:
        self._workspace = Path(workspace_dir)

    async def handle(self, ctx: SkillContext, *, command: str) -> str:
        _audit(ctx, "tool.bash", command=command)
        self._workspace.mkdir(parents=True, exist_ok=True)
        # UTF-16LE base64: immune to quoting / code-page mangling on Windows
        encoded = base64.b64encode(command.encode("utf-16le")).decode("ascii")
        cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                cwd=str(self._workspace),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=BASH_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            return f"command timed out after {BASH_TIMEOUT_S}s"
        text = result.stdout.decode("utf-8", errors="replace").rstrip("\r\n")
        if result.returncode != 0:
            text = f"[exit code {result.returncode}]\n" + text
        if len(text) > BASH_OUTPUT_LIMIT:
            text = text[:BASH_OUTPUT_LIMIT] + f"\n...[truncated, total {len(text)} chars]"
        return text
