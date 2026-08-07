"""内置工作区工具：read / write / edit / bash。

四个工具都限定在单一工作区目录（默认 `./workspace`，与 `data/` 同级）。路径参数
相对工作区根目录解析；每次访问都做越界校验，确保解析后的路径不能逃出工作区。
bash 以工作区为 CWD 运行 PowerShell。每次调用都会写入审计日志（tools.log），
记录调用用户 + 会话 + 命令/路径。
"""

from __future__ import annotations

import asyncio
import base64
import re
import subprocess
import time
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
    """校验工作区相对路径，返回解析后的绝对路径。

    绝对路径、空字符串、或解析后逃出工作区（如 `..` 穿越）都会抛 ValueError。
    这是所有文件操作的安全边界——先 resolve 再判断是否仍位于工作区内。"""
    p = Path(rel)
    if not rel or p.is_absolute() or p.anchor:
        raise ValueError(f"invalid workspace path: {rel!r}")
    root = workspace.resolve()
    resolved = (workspace / p).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"path escapes workspace: {rel!r}")
    return resolved


def _audit(ctx: SkillContext, event: str, **kw: Any) -> None:
    """审计日志：把"谁（user）+ 哪个会话（session_id）+ 干了什么（command/path）"
    写入 tools.log。这是工作区工具的安全兜底——即便 bash 被绝对路径绕过沙箱，
    事后也能据此追溯是谁在服务器上执行了哪条命令。"""
    user_id = getattr(ctx.user, "id", None)
    _log.info(event, user=user_id, session_id=ctx.session_id or None, **kw)


def cleanup_workspace(workspace_dir: str | Path, retention_days: int) -> int:
    """删除工作区中超过保留期的生成文件，再剪除被清空的目录。

    关键点：删除目录内的文件会刷新目录的 mtime（变为当前时间），所以空目录要按
    "是否为空"剪除，而不是按时间。工作区根目录本身保留。返回删除数量。
    retention_days <= 0 时禁用清理。"""
    if retention_days <= 0:
        return 0
    root = Path(workspace_dir)
    if not root.is_dir():
        return 0
    cutoff = time.time() - retention_days * 86400
    removed = 0
    # 第一遍：自底向上删除超期的旧文件（先文件后目录，目录留到第二遍）
    for p in sorted(root.rglob("*"), key=lambda x: len(x.parts), reverse=True):
        if p.is_dir():
            continue
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                removed += 1
        except OSError:
            pass  # 文件被占用 → 跳过
    # 第二遍：剪除被第一遍清空的目录（rmdir 只在目录为空时成功）
    for p in sorted(root.rglob("*"), key=lambda x: len(x.parts), reverse=True):
        if not p.is_dir():
            continue
        try:
            p.rmdir()
            removed += 1
        except OSError:
            pass  # 目录非空 → 保留
    if removed:
        _log.info("workspace.cleanup", removed=removed, retention_days=retention_days)
    return removed


def _split_path_heading(path: str) -> tuple[str, str | None]:
    """拆分 `file#heading` 为 (file, heading)。

    `#` 后为空标题 → ""（表示要目录 TOC）；完全没有 `#` → None（读整个文件）。
    用 None 与 "" 区分"无标题参数"与"显式要目录"，避免空串被当作假值跳过。"""
    if "#" in path:
        file_part, heading = path.rsplit("#", 1)
        return file_part, heading
    return path, None


def _extract_section(text: str, heading: str) -> str | None:
    """返回从匹配标题到下一个同级/更高级标题之间的段落。

    先精确匹配 `## name`；找不到再大小写不敏感的包含匹配（处理模糊型号名）。
    空标题返回所有 1/2 级标题的目录 TOC。找不到标题返回 None。
    作用：让 read 只需把某系列/某模块的段落取进上下文，避免整份大参考文件占满上下文。"""
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
        """解析读路径：要么是工作区相对路径，要么是 `@skill/<name>/<子目录>/<file>`。

        `@skill/` 形式把路径限定在对应 skill 目录内（references/、assets/ 等——只读的
        包内容），同样做 resolve + is_relative_to 越界校验，防止读到 skill 目录之外。"""
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
        _audit(ctx, "tool.bash", command=command)  # 先审计再执行，确保每条命令留痕
        self._workspace.mkdir(parents=True, exist_ok=True)
        # 用 UTF-16LE base64 编码命令：规避 Windows 上引号转义与中文代码页乱码
        encoded = base64.b64encode(command.encode("utf-16le")).decode("ascii")
        cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]
        try:
            # 子进程放线程池执行，避免阻塞事件循环；stdout+stderr 合并返回给 LLM
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                cwd=str(self._workspace),  # cwd 锁在工作区，但绝对路径仍可越界（风险已接受，靠审计兜底）
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
