"""Heurystyka ligi z web_search vs profil."""

from __future__ import annotations

import pytest

from backend.services.league_hint import (
    _search_blob,
    league_mismatch_heuristic,
)


def test_league_mismatch_when_not_in_blob():
    m, a = league_mismatch_heuristic("Season One", "path of exile two new content only")
    assert m is True and a is True


def test_league_match_when_in_blob():
    m, a = league_mismatch_heuristic("Fury", "path of exile fury league patch")
    assert m is False and a is False


def test_empty_profile_league_no_mismatch():
    m, a = league_mismatch_heuristic("", "anything")
    assert m is False and a is False


def test_search_blob_joins_fields():
    b = _search_blob(
        {
            "ok": True,
            "heading": "H",
            "abstract": "A",
            "related_texts": ["R1"],
            "instant_answer": "IA",
        }
    )
    assert "h" in b and "a" in b and "r1" in b and "ia" in b
