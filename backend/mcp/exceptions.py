"""Wyjątki narzędzi MCP (rate limit, itp.)."""

from __future__ import annotations


class RateLimitedError(Exception):
    """Przekroczono limit wywołań w oknie czasu (MCP-T-03)."""


__all__ = ["RateLimitedError"]
