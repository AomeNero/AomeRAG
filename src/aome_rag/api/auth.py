"""v1 auth: trust an `X-User-Id` header set by a gateway, or resolve a bearer token via
AUTH_TOKENS (entries like "userid:displayname"). No SSO/roles in v1."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel

from aome_rag.config import Settings, get_settings


class User(BaseModel):
    id: str
    display_name: str = ""


def _token_map(settings: Settings) -> dict[str, tuple[str, str]]:
    """Parse AUTH_TOKENS "userid:displayname,..." into {token: (id, name)} (token==userid)."""
    out: dict[str, tuple[str, str]] = {}
    for entry in (settings.auth_tokens.split(",") if settings.auth_tokens else []):
        entry = entry.strip()
        if not entry:
            continue
        if ":" in entry:
            uid, name = entry.split(":", 1)
        else:
            uid, name = entry, entry
        out[uid.strip()] = (uid.strip(), name.strip())
    return out


def get_current_user(
    x_user_id: str | None = Header(None, alias="X-User-Id"),
    x_user_name: str | None = Header(None, alias="X-User-Name"),
    authorization: str | None = Header(None),
    settings: Settings = Depends(get_settings),
) -> User:
    if x_user_id:
        return User(id=x_user_id, display_name=(x_user_name or x_user_id))
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        mapping = _token_map(settings)
        if token in mapping:
            uid, name = mapping[token]
            return User(id=uid, display_name=name)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="not authenticated (provide X-User-Id or a bearer token)",
    )
