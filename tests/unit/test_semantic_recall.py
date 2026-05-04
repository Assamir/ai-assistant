from __future__ import annotations

import pytest

from backend.memory.semantic_recall import SemanticRecall


def test_semantic_recall_roundtrip_conversations():
    sr = SemanticRecall()
    sr.add_conversation_chunks(
        ids=["a", "b"],
        documents=["unique_snippet_alpha_xyz", "other_beta_story"],
    )
    hits = sr.recall_conversations("unique_snippet_alpha_xyz", k=2)
    assert "unique_snippet_alpha_xyz" in hits


def test_semantic_recall_knowledge():
    sr = SemanticRecall()
    sr.add_knowledge_chunks(ids=["k1"], documents=["unique_kb_flask_boss_notes"])
    hits = sr.recall_knowledge("unique_kb_flask_boss_notes", k=1)
    assert hits == ["unique_kb_flask_boss_notes"]
