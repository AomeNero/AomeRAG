from fastapi.testclient import TestClient

from aome_rag.config import Settings
from aome_rag.main import create_app


def test_health_ok(tmp_path) -> None:
    # isolated settings so the test never touches the developer's ./data or .env
    settings = Settings(
        _env_file=None,
        sqlite_path=str(tmp_path / "s.db"),
        zvec_path=str(tmp_path / "col"),
        skills_dir=str(tmp_path / "sk"),
    )
    with TestClient(create_app(settings=settings)) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
