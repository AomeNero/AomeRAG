import pytest
from fastapi import HTTPException

from aome_rag.api.auth import User, get_current_user
from aome_rag.config import Settings


def _settings(auth_tokens: str = "") -> Settings:
    s = Settings()
    s.auth_tokens = auth_tokens
    return s


def test_no_credentials_unauthorized() -> None:
    with pytest.raises(HTTPException) as ei:
        get_current_user(
            x_user_id=None, x_user_name=None, authorization=None, settings=_settings()
        )
    assert ei.value.status_code == 401


def test_x_user_id_trusted() -> None:
    u = get_current_user(
        x_user_id="alice", x_user_name="Alice", authorization=None, settings=_settings()
    )
    assert isinstance(u, User) and u.id == "alice" and u.display_name == "Alice"


def test_bearer_token_resolved() -> None:
    u = get_current_user(
        x_user_id=None,
        x_user_name=None,
        authorization="Bearer bob",  # token == userid (v1 allowlist)
        settings=_settings(auth_tokens="bob:Bob,carol:Carol"),
    )
    assert u.id == "bob" and u.display_name == "Bob"


def test_bad_bearer_unauthorized() -> None:
    with pytest.raises(HTTPException) as ei:
        get_current_user(
            x_user_id=None,
            x_user_name=None,
            authorization="Bearer nope",
            settings=_settings(auth_tokens="bob:Bob"),
        )
    assert ei.value.status_code == 401
