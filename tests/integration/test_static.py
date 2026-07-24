"""Production static serving: when web/dist exists, FastAPI serves the SPA at / while API
routes still take precedence. Missing dist → API-only (dev uses Vite)."""

import pytest
from fastapi.testclient import TestClient

from aome_rag.config import Settings
from aome_rag.main import create_app

pytestmark = pytest.mark.integration


def _settings(tmp_path, frontend_dist: str) -> Settings:
    return Settings(
        _env_file=None,
        frontend_dist=frontend_dist,
        sqlite_path=str(tmp_path / "s.db"),
        zvec_path=str(tmp_path / "col"),
        skills_dir=str(tmp_path / "sk"),
    )


def test_prod_serves_index_and_api_still_works(tmp_path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>spa</html>", encoding="utf-8")

    with TestClient(create_app(settings=_settings(tmp_path, str(dist)))) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert "spa" in r.text
        # API routes are registered before the catch-all mount, so they still win
        assert client.get("/health").json() == {"status": "ok"}


def test_no_dist_means_api_only(tmp_path) -> None:
    with TestClient(create_app(settings=_settings(tmp_path, str(tmp_path / "nope")))) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/").status_code == 404  # no static mount → API 404
