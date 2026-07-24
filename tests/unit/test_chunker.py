from aome_rag.ingestion.chunker import Chunker


def test_structural_split_by_headings() -> None:
    md = """# Title

Intro paragraph.

## Section A

Content of A.

## Section B

Content of B with **bold**.
"""
    chunks = Chunker().split(md, source_doc="doc.md")
    paths = [c["heading_path"] for c in chunks]
    texts = [c["text"] for c in chunks]
    assert paths == ["Title", "Title > Section A", "Title > Section B"]
    assert "Intro paragraph." in texts[0]
    assert "Content of A." in texts[1]
    assert "Content of B" in texts[2]
    # chunk_index assigned sequentially
    assert [c["chunk_index"] for c in chunks] == [0, 1, 2]
    assert all(c["source_doc"] == "doc.md" for c in chunks)


def test_long_section_falls_back_to_windows() -> None:
    body = "para.\n\n" * 400  # ~2400 chars, well over max
    md = f"# Big\n\n{body}"
    chunker = Chunker(target_chars=500, max_chars=800, overlap=80)
    chunks = chunker.split(md, source_doc="big.md")
    assert len(chunks) > 1
    # all share the heading path; none exceeds max (hard-split guards it)
    assert all(c["heading_path"] == "Big" for c in chunks)
    assert all(len(c["text"]) <= 800 for c in chunks)


def test_empty_input() -> None:
    assert Chunker().split("", source_doc="x.md") == []
    assert Chunker().split("   \n\n  ", source_doc="x.md") == []
