"""FastAPI 依赖：从 app.state 取共享服务。"""

from __future__ import annotations

from fastapi import Request

from .auth import get_current_user  # re-export for convenience

__all__ = ["get_state", "get_current_user"]


def get_state(request: Request):
    return request.app.state
