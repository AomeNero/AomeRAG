from aome_rag.agent.context import assemble_system_prompt
from aome_rag.agent.prompts import PROMPT_FILE, load_base_prompt


def test_load_base_prompt_reads_md_file() -> None:
    assert PROMPT_FILE.is_file()
    text = load_base_prompt()
    assert "AomeRAG" in text  # the editable .md content is loaded


def test_assemble_base_then_fragments() -> None:
    out = assemble_system_prompt(["FRAGMENT-X", "", "FRAGMENT-Y"])
    assert "AomeRAG" in out
    assert "FRAGMENT-X" in out and "FRAGMENT-Y" in out  # empty fragments dropped
    assert out.index("AomeRAG") < out.index("FRAGMENT-X")  # base precedes fragments
