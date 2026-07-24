import pytest

from aome_rag.ingestion.parser import SUPPORTED_EXTS, Parser, UnsupportedFile


def test_md_read_directly() -> None:
    md = b"# Title\n\nhello **world** \xe4\xb8\xad\xe6\x96\x87"  # utf-8 chinese
    out = Parser().parse("doc.md", md)
    assert out == md.decode("utf-8")  # verbatim, no markitdown processing


def test_txt_via_markitdown() -> None:
    out = Parser().parse("doc.txt", b"plain text line one")
    assert "plain text line one" in out


def test_unsupported_raises() -> None:
    with pytest.raises(UnsupportedFile):
        Parser().parse("image.png", b"\x89PNG\r\n")


def test_markdown_alias_ext() -> None:
    assert Parser().parse("doc.markdown", b"# x").startswith("# x")


def test_supported_exts_covers_common_docs() -> None:
    for ext in (".md", ".pdf", ".docx", ".pptx", ".xlsx", ".html", ".txt"):
        assert ext in SUPPORTED_EXTS
