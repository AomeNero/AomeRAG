"""Tests for the file-logging setup (logs/app/ + logs/access/, daily rotation)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
import structlog

from aome_rag.config import Settings
from aome_rag.logging import APP_MODULES, configure_logging


@pytest.fixture(autouse=True)
def _cleanup_logging():
    """Detach managed handlers after each test; restore console-only behaviour."""
    yield
    configure_logging("INFO", log_dir=None)


def test_config_defaults() -> None:
    f = Settings.model_fields
    assert f["log_dir"].default == "./logs"
    assert f["log_to_file"].default is True
    assert f["log_app_to_file"].default is True
    assert f["log_access_to_file"].default is True
    assert f["log_retention_days"].default == 30


def test_log_dir_resolved_absolute() -> None:
    assert Path(Settings().log_dir).is_absolute()


def test_console_only_writes_nothing(tmp_path) -> None:
    configure_logging("INFO", log_dir=None)
    assert list(tmp_path.iterdir()) == []


def test_master_switch_off_creates_nothing(tmp_path) -> None:
    configure_logging("INFO", log_dir=str(tmp_path / "logs"), log_to_file=False)
    assert not (tmp_path / "logs").exists()


def test_default_on_creates_app_and_access(tmp_path) -> None:
    configure_logging("INFO", log_dir=str(tmp_path))
    assert (tmp_path / "app").is_dir()
    assert (tmp_path / "access").is_dir()
    for mod in APP_MODULES:
        assert (tmp_path / "app" / f"{mod}.log").is_file(), f"missing app/{mod}.log"


def test_module_log_routed_to_its_file(tmp_path) -> None:
    configure_logging("INFO", log_dir=str(tmp_path))
    structlog.get_logger("aome_rag.api.routes_chat").info("hello.world", n=42)
    structlog.get_logger("aome_rag.agent.loop").info("agent.step")
    api = (tmp_path / "app" / "api.log").read_text(encoding="utf-8")
    agent = (tmp_path / "app" / "agent.log").read_text(encoding="utf-8")
    assert "hello.world" in api and "n=42" in api
    assert "agent.step" in agent
    assert "agent.step" not in api


def test_secrets_redacted_in_file(tmp_path) -> None:
    configure_logging("INFO", log_dir=str(tmp_path))
    structlog.get_logger("aome_rag.api").info("req", api_key="sk-should-not-leak")
    content = (tmp_path / "app" / "api.log").read_text(encoding="utf-8")
    assert "sk-should-not-leak" not in content
    assert "api_key=***" in content


def test_app_off_skips_app_files(tmp_path) -> None:
    configure_logging("INFO", log_dir=str(tmp_path), log_app_to_file=False)
    assert not (tmp_path / "app").exists()
    assert (tmp_path / "access").is_dir()


def test_access_off_skips_access_dir(tmp_path) -> None:
    configure_logging("INFO", log_dir=str(tmp_path), log_access_to_file=False)
    assert (tmp_path / "app").is_dir()
    assert not (tmp_path / "access").exists()


def test_both_off_creates_no_files(tmp_path) -> None:
    configure_logging(
        "INFO", log_dir=str(tmp_path),
        log_app_to_file=False, log_access_to_file=False,
    )
    assert not (tmp_path / "app").exists()
    assert not (tmp_path / "access").exists()


def test_uvicorn_access_writes_file(tmp_path) -> None:
    configure_logging("INFO", log_dir=str(tmp_path))
    logger = logging.getLogger("uvicorn.access")
    assert any(hasattr(h, "baseFilename") for h in logger.handlers)
    logger.info(
        '%s - "%s %s HTTP/%s" %d',
        "127.0.0.1:1234", "GET", "/", "1.1", 200,
    )
    content = (tmp_path / "access" / "access.log").read_text(encoding="utf-8")
    assert '127.0.0.1:1234 - "GET / HTTP/1.1" 200' in content


def test_uvicorn_error_writes_app_uvicorn(tmp_path) -> None:
    configure_logging("INFO", log_dir=str(tmp_path))
    logging.getLogger("uvicorn.error").error("boom")
    content = (tmp_path / "app" / "uvicorn.log").read_text(encoding="utf-8")
    assert "boom" in content
