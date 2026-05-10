"""Testy jednostkowe ThreadClassifier i ComplexityClassifier."""

import pytest

from backend.core.complexity_classifier import ComplexityClassifier
from backend.core.thread_classifier import (
    ClassificationResult,
    ThreadClassifier,
    _jaccard,
    _token_set,
)


class TestTokenSet:
    def test_basic(self):
        tokens = _token_set("gra najlepsza buduje postać")
        assert "gra" in tokens
        assert "najlepsza" in tokens

    def test_filters_stop_words(self):
        tokens = _token_set("a ale bo czy i")
        assert len(tokens) == 0

    def test_min_length(self):
        tokens = _token_set("aa bb ccc dddd")
        assert "ccc" in tokens
        assert "dddd" in tokens
        assert "aa" not in tokens
        assert "bb" not in tokens


class TestJaccard:
    def test_identical(self):
        a = frozenset(["ala", "ma", "kota"])
        assert _jaccard(a, a) == 1.0

    def test_disjoint(self):
        a = frozenset(["ala"])
        b = frozenset(["kota"])
        assert _jaccard(a, b) == 0.0

    def test_partial(self):
        a = frozenset(["ala", "kota"])
        b = frozenset(["ala", "psa"])
        score = _jaccard(a, b)
        assert 0.0 < score < 1.0

    def test_empty(self):
        assert _jaccard(frozenset(), frozenset()) == 1.0


class TestComplexityClassifier:
    def setup_method(self):
        self.clf = ComplexityClassifier()

    def test_simple_greeting(self):
        assert self.clf.classify("cześć") == "simple"

    def test_simple_command(self):
        assert self.clf.classify("idź spać") == "simple"

    def test_complex_analyze(self):
        assert self.clf.classify("zbadaj temat tier listy ADC na aktualnym patchu") == "complex"

    def test_complex_plan(self):
        assert self.clf.classify("zaplanuj mi team comp na sezon 14 ligi srebrnej") == "complex"

    def test_complex_compare(self):
        assert self.clf.classify("sprawdź i porównaj Ashę i Miss Fortune jako ADC") == "complex"

    def test_simple_time(self):
        assert self.clf.classify("która godzina?") == "simple"

    def test_simple_ok(self):
        assert self.clf.classify("ok") == "simple"


class TestClassificationResult:
    def test_fields(self):
        r = ClassificationResult(kind="new", thread_id=None, confidence=1.0)
        assert r.kind == "new"
        assert r.thread_id is None
        assert r.confidence == 1.0

    def test_continuation(self):
        r = ClassificationResult(kind="continuation", thread_id=42, confidence=0.8)
        assert r.kind == "continuation"
        assert r.thread_id == 42


@pytest.mark.asyncio
async def test_classifier_new_thread_when_no_active(tmp_path):
    db = str(tmp_path / "test.db")
    from backend.db.migration_runner import MigrationRunner

    MigrationRunner(db).run_migrations()

    clf = ThreadClassifier(db)
    result = await clf.classify("hej jak masz", active_thread_id=None)
    assert result.kind == "new"
    assert result.thread_id is None


@pytest.mark.asyncio
async def test_classifier_continuation_recent(tmp_path):
    db = str(tmp_path / "test.db")
    from backend.db.migration_runner import MigrationRunner
    from backend.db.repositories import ThreadRepository

    MigrationRunner(db).run_migrations()

    repo = ThreadRepository(db)
    thread_id = await repo.create_thread(title="Team comp engage LoL")
    await repo.update_thread(
        thread_id,
        topic_summary="Team comp wokół engage. Szukamy ADC.",
    )

    clf = ThreadClassifier(db)
    result = await clf.classify("jaki ADC pasuje do engage?", active_thread_id=thread_id)
    assert result.kind == "continuation"
    assert result.thread_id == thread_id
