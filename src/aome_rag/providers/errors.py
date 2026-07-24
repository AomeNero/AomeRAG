"""Provider-layer errors."""

from __future__ import annotations


class ProviderError(Exception):
    """Generic upstream / provider failure."""


class RateLimitError(ProviderError):
    """Upstream returned 429 and retries were exhausted."""


class ToolCallParseError(ProviderError):
    """The model's tool-call arguments were not valid JSON / not an object."""
