"""Provider 层错误。"""

from __future__ import annotations


class ProviderError(Exception):
    """通用的上游 / Provider 失败。"""


class RateLimitError(ProviderError):
    """上游返回 429 且重试已耗尽。"""


class ToolCallParseError(ProviderError):
    """模型的工具调用参数不是合法 JSON / 不是对象。"""
