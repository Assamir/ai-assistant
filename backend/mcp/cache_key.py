"""Klucz cache MCP: SHA256 narzędzia + kanoniczny JSON argumentów."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def canonical_mcp_cache_key(tool_name: str, params: Mapping[str, Any]) -> str:
    payload = {"tool": tool_name, "args": dict(params)}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


__all__ = ["canonical_mcp_cache_key"]
