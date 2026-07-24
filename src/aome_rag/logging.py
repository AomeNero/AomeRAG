"""Structured logging via structlog, with best-effort secret redaction."""

from __future__ import annotations

import logging

import structlog

# Substrings that mark a log key as sensitive → value is replaced with "***".
_SENSITIVE_HINTS = ("key", "token", "secret", "authorization", "password", "cookie")


def _redact_secrets(_logger, _name, event_dict: dict) -> dict:
    for key in list(event_dict):
        lk = key.lower()
        if any(hint in lk for hint in _SENSITIVE_HINTS):
            event_dict[key] = "***"
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog. Safe to call once at startup."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact_secrets,
            structlog.dev.ConsoleRenderer(colors=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        cache_logger_on_first_use=True,
    )
