"""Minimalny audyt wywołań narzędzi sieciowych — bez treści zapytania w plain text."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Mapping

_log = logging.getLogger(__name__)


def args_digest_prefix(arguments: Mapping[str, Any], *, nbytes: int = 16) -> str:
    """SHA-256 kanonicznego JSON argumentów — prefiks hex do korelacji logów."""
    canonical = json.dumps(dict(arguments), sort_keys=True, ensure_ascii=False)
    h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return h[: max(8, min(nbytes, len(h)))]


def log_mcp_network_call(tool_name: str, *, arguments: Mapping[str, Any], duration_ms: int, success: bool) -> None:
    _log.info(
        "mcp_network_call tool=%s duration_ms=%s ok=%s args_digest_prefix=%s",
        tool_name,
        duration_ms,
        success,
        args_digest_prefix(arguments),
    )


__all__ = ["args_digest_prefix", "log_mcp_network_call"]
