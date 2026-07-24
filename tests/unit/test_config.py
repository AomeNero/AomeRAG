from aome_rag.config import Settings


def test_defaults() -> None:
    # Inspect declared field defaults (not a constructed instance) so the test is immune
    # to a developer's .env overriding values.
    f = Settings.model_fields
    assert f["embed_dim"].default == 1024
    assert f["deepseek_model"].default == "deepseek-chat"
    assert f["max_iterations"].default == 6
    assert f["raw_dir"].default == "./raw"
    # bge-m3 via Ollama exposes dense only — keyword channel is Zvec FTS, not sparse.
    assert f["ollama_embed_model"].default == "bge-m3"


def test_env_override(monkeypatch) -> None:
    monkeypatch.setenv("ZVEC_PATH", "/tmp/zz")
    monkeypatch.setenv("MAX_ITERATIONS", "9")
    s = Settings()
    assert s.zvec_path == "/tmp/zz"
    assert s.max_iterations == 9
