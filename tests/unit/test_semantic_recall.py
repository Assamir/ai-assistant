from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from backend.memory.semantic_recall import SemanticRecall


@pytest.fixture
def memory_mode():
    """Block chromadb import so SemanticRecall initialises in list-fallback mode."""
    with patch.dict(sys.modules, {"chromadb": None}):
        yield


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


# ---------------------------------------------------------------------------
# prune_conversations — memory mode
# ---------------------------------------------------------------------------

def test_prune_conversations_removes_oldest_memory(memory_mode):
    sr = SemanticRecall(max_conversations=3)
    for i in range(5):
        sr.add_conversation_chunks(ids=[f"c{i}"], documents=[f"doc_{i}"])
    # max_conversations=3 → after each add auto-prune keeps newest 3
    assert len(sr._conv_docs) == 3
    assert sr._conv_docs == ["doc_2", "doc_3", "doc_4"]


def test_prune_conversations_noop_when_under_limit(memory_mode):
    sr = SemanticRecall(max_conversations=10)
    sr.add_conversation_chunks(ids=["a", "b"], documents=["x", "y"])
    assert len(sr._conv_docs) == 2


def test_prune_conversations_explicit_call(memory_mode):
    sr = SemanticRecall(max_conversations=0)  # auto-prune disabled
    for i in range(5):
        sr.add_conversation_chunks(ids=[f"c{i}"], documents=[f"doc_{i}"])
    assert len(sr._conv_docs) == 5
    sr.prune_conversations(2)
    assert len(sr._conv_docs) == 2
    assert sr._conv_docs == ["doc_3", "doc_4"]


def test_prune_conversations_ingest_seq_preserved_in_metadata(memory_mode):
    sr = SemanticRecall(max_conversations=100)
    sr.add_conversation_chunks(ids=["a", "b"], documents=["first", "second"])
    seqs = [m["ingest_seq"] for m in sr._conv_metas]
    assert seqs == [1, 2]


def test_prune_conversations_accepts_custom_metadatas(memory_mode):
    sr = SemanticRecall(max_conversations=100)
    sr.add_conversation_chunks(
        ids=["m1"],
        documents=["hello"],
        metadatas=[{"source": "user", "session_id": 42}],
    )
    m = sr._conv_metas[0]
    assert m["source"] == "user"
    assert m["session_id"] == 42
    assert "ingest_seq" in m


# ---------------------------------------------------------------------------
# prune_conversations — chroma mode
# ---------------------------------------------------------------------------

def test_prune_conversations_chroma_removes_oldest():
    try:
        import chromadb  # noqa: F401
    except Exception:
        pytest.skip("chromadb not usable")

    sr = SemanticRecall(max_conversations=3, collection_prefix="t_removes_oldest")
    for i in range(5):
        sr.add_conversation_chunks(ids=[f"c{i}"], documents=[f"doc_{i}"])
    count = sr._conv.count()
    assert count == 3


def test_prune_conversations_chroma_noop_when_under_limit():
    try:
        import chromadb  # noqa: F401
    except Exception:
        pytest.skip("chromadb not usable")

    sr = SemanticRecall(max_conversations=10, collection_prefix="t_noop_under_limit")
    sr.add_conversation_chunks(ids=["a", "b"], documents=["x", "y"])
    assert sr._conv.count() == 2


def test_prune_knowledge_base_unchanged(memory_mode):
    """prune_knowledge_base unaffected by conversations changes."""
    sr = SemanticRecall()
    for i in range(5):
        sr.add_knowledge_chunks(ids=[f"k{i}"], documents=[f"kb_{i}"])
    sr.prune_knowledge_base(3)
    assert len(sr._kb_docs) == 3
