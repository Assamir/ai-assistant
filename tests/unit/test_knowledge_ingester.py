"""KnowledgeIngester i rozszerzenia SemanticRecall (FIFO / where)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.memory.knowledge_ingester import KnowledgeDirectoryWatcher, KnowledgeIngester, chunk_text
from backend.memory.semantic_recall import SemanticRecall


def test_chunk_text_merges_paragraphs():
    t = "a.\n\nb.\n\nc."
    parts = chunk_text(t, max_chars=500, overlap=50)
    joined = "\n".join(parts)
    assert "a." in joined and "b." in joined and "c." in joined


def test_chunk_text_preserves_long_paragraph_splits():
    blob = "word " * 200
    parts = chunk_text(blob, max_chars=80, overlap=10)
    assert len(parts) >= 2
    assert all(len(x) <= 80 for x in parts)


@pytest.fixture
def recall():
    return SemanticRecall()


def test_ingest_writes_recall_knowledge(recall: SemanticRecall):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "note.md"
        p.write_text("unique_alpha_kb_phrase dla testu\n\nDrugi akapit.", encoding="utf-8")
        ing = KnowledgeIngester(recall, chunk_size=500, max_total_chunks=100)
        n = ing.ingest_directory(d)
        assert n >= 1
    hits = recall.recall_knowledge("unique_alpha_kb_phrase", k=2)
    assert any("unique_alpha_kb_phrase" in h for h in hits)


def test_ingest_replace_same_source_path(recall: SemanticRecall):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "doc.txt"
        p.write_text("stara treść xyz111", encoding="utf-8")
        ing = KnowledgeIngester(recall, chunk_size=200, max_total_chunks=100)
        ing.ingest_directory(d)
        p.write_text("nowa treść xyz222 unikat", encoding="utf-8")
        ing.ingest_directory(d)
    hits = recall.recall_knowledge("xyz222", k=2)
    assert hits
    old_hits = recall.recall_knowledge("xyz111", k=4)
    assert not any("xyz111" in h for h in old_hits)


def test_prune_knowledge_fifo(recall: SemanticRecall):
    with tempfile.TemporaryDirectory() as d:
        ing = KnowledgeIngester(recall, chunk_size=50, chunk_overlap=0, max_total_chunks=3)
        for i in range(5):
            (Path(d) / f"f{i}.md").write_text(f"segment {i} " + "x" * 40, encoding="utf-8")
        ing.ingest_directory(d)
    all_hits = recall.recall_knowledge("segment", k=10)
    assert len(all_hits) <= 3


def test_remove_knowledge_where():
    sr = SemanticRecall()
    sr.add_knowledge_chunks(
        ids=["a", "b"],
        documents=["unique_kb_doc_alpha", "unique_kb_doc_beta"],
        metadatas=[{"source_path": "x.md", "chunk_index": 0}, {"source_path": "y.md", "chunk_index": 0}],
    )
    n = sr.remove_knowledge_chunks_where({"source_path": "x.md"})
    assert n == 1
    alpha_hits = sr.recall_knowledge("unique_kb_doc_alpha", k=4)
    assert not any("unique_kb_doc_alpha" in h for h in alpha_hits)
    beta_hits = sr.recall_knowledge("unique_kb_doc_beta", k=4)
    assert any("unique_kb_doc_beta" in h for h in beta_hits)


def test_watcher_start_stop_registers_observer():
    sr = SemanticRecall()
    ing = KnowledgeIngester(sr, max_total_chunks=50)
    with tempfile.TemporaryDirectory() as d:
        w = KnowledgeDirectoryWatcher(ing, d, debounce_seconds=0.05)
        fake_obs = MagicMock()
        with patch("watchdog.observers.Observer", return_value=fake_obs):
            w.start()
        fake_obs.start.assert_called_once()
        w.stop()
        fake_obs.stop.assert_called_once()
