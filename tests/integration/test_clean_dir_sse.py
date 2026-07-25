"""POST /clean/dir end-to-end: raw-data .md → md-data .md with front-matter."""

import json

import pytest
from fastapi.testclient import TestClient

from aome_rag.config import Settings
from aome_rag.main import create_app
from tests.fakes import FakeProvider

pytestmark = pytest.mark.integration


def test_clean_dir_produces_md_with_frontmatter(tmp_path) -> None:
    raw = tmp_path / "raw-data"
    raw.mkdir()
    (raw / "test.md").write_text("# Hello\n\nSome content here.", encoding="utf-8")

    md = tmp_path / "md-data"
    settings = Settings(
        _env_file=None,
        raw_data_dir=str(raw),
        md_data_dir=str(md),
        sqlite_path=str(tmp_path / "s.db"),
        zvec_path=str(tmp_path / "col"),
        skills_dir=str(tmp_path / "sk"),
        embed_dim=8,
    )
    app = create_app(settings=settings, overrides={"provider": FakeProvider()})
    with TestClient(app) as client:
        with client.stream("POST", "/clean/dir", headers={"X-User-Id": "alice"}) as resp:
            assert resp.status_code == 200
            events = [
                json.loads(line[5:].strip())
                for line in resp.iter_lines()
                if line.startswith("data:")
            ]

    types = [e["type"] for e in events]
    assert types[0] == "scan"
    assert types[-1] == "summary"
    assert events[-1]["n_docs"] >= 1
    assert events[-1]["n_failed"] == 0

    out = (md / "test.md").read_text(encoding="utf-8")
    assert out.startswith("---\n")
    assert 'title: "test"' in out
    assert "# Hello" in out  # body preserved


def test_clean_dir_requires_auth(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        raw_data_dir=str(tmp_path / "raw"),
        md_data_dir=str(tmp_path / "md"),
        sqlite_path=str(tmp_path / "s.db"),
        zvec_path=str(tmp_path / "col"),
        skills_dir=str(tmp_path / "sk"),
        embed_dim=8,
    )
    app = create_app(settings=settings, overrides={"provider": FakeProvider()})
    with TestClient(app) as client:
        r = client.post("/clean/dir")
    assert r.status_code == 401
