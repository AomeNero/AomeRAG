"""Tests for the built-in workspace tools (read/write/edit/bash)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from aome_rag.config import Settings
from aome_rag.tools.base import SkillContext
from aome_rag.tools.skill_loader import SkillLoaderSkill
from aome_rag.tools.workspace import (
    MAX_READ_BYTES,
    MAX_WRITE_BYTES,
    BashTool,
    EditTool,
    ReadTool,
    WriteTool,
    _resolve_workspace_path,
    cleanup_workspace,
)


def ctx() -> SkillContext:
    return SkillContext(user=None, session_id="test")


def make_ws(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


# ---------- config ----------

def test_workspace_dir_config_default() -> None:
    f = Settings.model_fields
    assert f["workspace_dir"].default == "./workspace"


def test_workspace_dir_resolved_absolute() -> None:
    assert Path(Settings().workspace_dir).is_absolute()


# ---------- path validation ----------

def test_resolve_rejects_escape(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    with pytest.raises(ValueError, match="escapes"):
        _resolve_workspace_path(ws, "../secret.txt")
    with pytest.raises(ValueError, match="escapes"):
        _resolve_workspace_path(ws, "sub/../../secret.txt")


def test_resolve_rejects_absolute(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    with pytest.raises(ValueError):
        _resolve_workspace_path(ws, str(tmp_path / "outside.txt"))
    with pytest.raises(ValueError):
        _resolve_workspace_path(ws, "C:\\Windows\\win.ini")


# ---------- read ----------

async def test_read_basic(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    (ws / "notes.md").write_text("# hi\nhello world", encoding="utf-8")
    out = await ReadTool(ws).handle(ctx(), path="notes.md")
    assert "hello world" in out


async def test_read_missing_file(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    out = await ReadTool(ws).handle(ctx(), path="nope.md")
    assert "not found" in out


async def test_read_escape_rejected(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    out = await ReadTool(ws).handle(ctx(), path="../../etc/passwd")
    assert "escapes" in out


async def test_read_binary_rejected(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    (ws / "blob.bin").write_bytes(b"\x00\x01\x02\xff")
    out = await ReadTool(ws).handle(ctx(), path="blob.bin")
    assert "not a UTF-8 text file" in out


async def test_read_too_large(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    (ws / "big.txt").write_bytes(b"a" * (MAX_READ_BYTES + 1))
    out = await ReadTool(ws).handle(ctx(), path="big.txt")
    assert "too large" in out


# ---------- read: @skill/ reference files ----------

def _skill_ref_tool(tmp_path: Path) -> ReadTool:
    skills_dir = tmp_path / "skills"
    ref_dir = skills_dir / "products" / "references"
    ref_dir.mkdir(parents=True)
    (ref_dir / "data.md").write_text(
        "# Title\n## SeriesA\ncontent A\n## SeriesB\ncontent B\n",
        encoding="utf-8",
    )
    assets = skills_dir / "products" / "assets" / "luaTemplate"
    assets.mkdir(parents=True)
    (assets / "PowerOn.lua").write_text("-- template\nfunction init() end", encoding="utf-8")
    return ReadTool(tmp_path / "ws", skills_dir=skills_dir)


async def test_read_skill_section(tmp_path: Path) -> None:
    out = await _skill_ref_tool(tmp_path).handle(
        ctx(), path="@skill/products/references/data.md#SeriesA"
    )
    assert "content A" in out
    assert "content B" not in out


async def test_read_skill_toc(tmp_path: Path) -> None:
    out = await _skill_ref_tool(tmp_path).handle(
        ctx(), path="@skill/products/references/data.md#"
    )
    assert "SeriesA" in out and "SeriesB" in out


async def test_read_skill_fuzzy_heading(tmp_path: Path) -> None:
    out = await _skill_ref_tool(tmp_path).handle(
        ctx(), path="@skill/products/references/data.md#Series"
    )
    assert "content A" in out


async def test_read_skill_asset(tmp_path: Path) -> None:
    out = await _skill_ref_tool(tmp_path).handle(
        ctx(), path="@skill/products/assets/luaTemplate/PowerOn.lua"
    )
    assert "function init" in out


async def test_read_skill_escape_rejected(tmp_path: Path) -> None:
    rt = _skill_ref_tool(tmp_path)
    out = await rt.handle(ctx(), path="@skill/products/../../secret.md")
    assert "escapes" in out
    out2 = await rt.handle(ctx(), path="@skill/../other/references/x.md")
    assert "invalid" in out2


def test_skill_loader_desc_from_frontmatter(tmp_path: Path) -> None:
    p = tmp_path / "s.md"
    p.write_text(
        "---\nname: x\ndescription: 触发条件：提到 XXX 时使用\n---\n# 标题\n内容",
        encoding="utf-8",
    )
    assert SkillLoaderSkill._extract_desc(p) == "触发条件：提到 XXX 时使用"


def test_skill_loader_desc_fallback_to_heading(tmp_path: Path) -> None:
    p = tmp_path / "s.md"
    p.write_text("# 纯标题\n内容", encoding="utf-8")
    assert SkillLoaderSkill._extract_desc(p) == "纯标题"


# ---------- workspace cleanup ----------

def _set_mtime(p: Path, days_ago: float) -> None:
    ts = time.time() - days_ago * 86400
    os.utime(p, (ts, ts))


def test_cleanup_removes_old_keeps_fresh(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    old_dir = ws / "Recipe_old"
    old_dir.mkdir()
    (old_dir / "a.lua").write_text("x", encoding="utf-8")
    fresh = ws / "Recipe_fresh"
    fresh.mkdir()
    (fresh / "b.lua").write_text("y", encoding="utf-8")
    _set_mtime(old_dir / "a.lua", 10)
    _set_mtime(old_dir, 10)
    _set_mtime(fresh / "b.lua", 0)
    _set_mtime(fresh, 0)
    removed = cleanup_workspace(ws, retention_days=7)
    assert removed >= 2  # a.lua + emptied old_dir
    assert not old_dir.exists()
    assert fresh.exists() and (fresh / "b.lua").exists()


def test_cleanup_disabled_when_zero(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    (ws / "old.txt").write_text("x", encoding="utf-8")
    _set_mtime(ws / "old.txt", 30)
    assert cleanup_workspace(ws, retention_days=0) == 0
    assert (ws / "old.txt").exists()


def test_cleanup_keeps_workspace_root(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    (ws / "old.txt").write_text("x", encoding="utf-8")
    _set_mtime(ws / "old.txt", 30)
    cleanup_workspace(ws, retention_days=7)
    assert ws.is_dir()  # root kept


# ---------- write ----------

async def test_write_creates_dirs(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    out = await WriteTool(ws).handle(ctx(), path="sub/deep/notes.md", content="hello")
    assert "wrote" in out
    assert (ws / "sub" / "deep" / "notes.md").read_text(encoding="utf-8") == "hello"


async def test_write_overwrites(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    (ws / "a.txt").write_text("old", encoding="utf-8")
    await WriteTool(ws).handle(ctx(), path="a.txt", content="new")
    assert (ws / "a.txt").read_text(encoding="utf-8") == "new"


async def test_write_escape_rejected(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    out = await WriteTool(ws).handle(ctx(), path="../evil.txt", content="x")
    assert "escapes" in out
    assert not (tmp_path / "evil.txt").exists()


async def test_write_too_large(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    out = await WriteTool(ws).handle(ctx(), path="big.txt", content="x" * (MAX_WRITE_BYTES + 1))
    assert "too large" in out


# ---------- edit ----------

async def test_edit_replaces_all(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    (ws / "t.txt").write_text("foo foo bar foo", encoding="utf-8")
    out = await EditTool(ws).handle(ctx(), path="t.txt", find="foo", replace="baz")
    assert "3" in out
    assert (ws / "t.txt").read_text(encoding="utf-8") == "baz baz bar baz"


async def test_edit_not_found(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    (ws / "t.txt").write_text("hello", encoding="utf-8")
    out = await EditTool(ws).handle(ctx(), path="t.txt", find="nope", replace="x")
    assert "not found" in out
    assert (ws / "t.txt").read_text(encoding="utf-8") == "hello"


async def test_edit_escape_rejected(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    out = await EditTool(ws).handle(ctx(), path="../t.txt", find="a", replace="b")
    assert "escapes" in out


# ---------- bash ----------

async def test_bash_output(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    out = await BashTool(ws).handle(ctx(), command="Write-Output hello")
    assert "hello" in out


async def test_bash_cwd_is_workspace(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    out = await BashTool(ws).handle(ctx(), command="(Get-Location).Path")
    assert str(ws).lower() in out.lower()


async def test_bash_nonzero_exit(tmp_path: Path) -> None:
    ws = make_ws(tmp_path)
    out = await BashTool(ws).handle(ctx(), command="Exit 3")
    assert "exit code 3" in out
