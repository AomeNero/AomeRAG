"""LLM provider abstraction boundary.

This package knows only the neutral internal message model plus each adapter's own wire
format. The agent loop imports `base.LLMProvider` only — never a concrete provider.
"""
