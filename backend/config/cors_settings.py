"""Parametry middleware CORS (originy z ENV, zgodnie ze spec — wildcard wyłącza credentials)."""

from __future__ import annotations

import os
from typing import Any


def cors_middleware_params() -> dict[str, Any]:
    """
    ASSYSTENT_CORS_ORIGINS:
    - puste lub ``*`` → allow_origins=['*'], allow_credentials=False
    - lista po przecinku (np. http://localhost:5173,http://127.0.0.1:5173) → jawne originy + credentials
    """
    raw = os.environ.get("ASSYSTENT_CORS_ORIGINS", "").strip()
    if not raw or raw == "*":
        return {
            "allow_origins": ["*"],
            "allow_credentials": False,
            "allow_methods": ["*"],
            "allow_headers": ["*"],
        }
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if not origins:
        return {
            "allow_origins": ["*"],
            "allow_credentials": False,
            "allow_methods": ["*"],
            "allow_headers": ["*"],
        }
    return {
        "allow_origins": origins,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }


__all__ = ["cors_middleware_params"]
