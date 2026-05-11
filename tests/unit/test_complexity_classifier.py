"""ComplexityClassifier — heurystyka klasyfikująca pytania na simple/complex."""

from __future__ import annotations

import pytest

from backend.core.complexity_classifier import ComplexityClassifier


@pytest.fixture
def clf() -> ComplexityClassifier:
    return ComplexityClassifier()


@pytest.mark.parametrize("text", [
    "cześć",
    "dzięki",
    "tak",
    "która godzina?",
    "idź spać",
    "obudź się",
])
def test_simple_short_phrases(clf: ComplexityClassifier, text: str):
    assert clf.classify(text) == "simple"


@pytest.mark.parametrize("text", [
    "polecasz jakiś build pod waystone'y?",
    "co lepsze, witch infernalist czy sorc?",
    "porównaj te dwa buildy",
    "doradź mi jak grać monkiem na endgame",
    "jaki build pod ranger jest najlepszy?",
    "wytłumacz mi mechanikę spirit reservation",
    "plusy i minusy gemling legionnaire",
    "jak rozwinąć tę postać dalej?",
    "czy warto teraz farmić waystoney t14?",
    "zaproponuj mi taktykę na ten boss fight",
])
def test_gaming_questions_are_complex(clf: ComplexityClassifier, text: str):
    assert clf.classify(text) == "complex", f"expected complex for: {text!r}"


@pytest.mark.parametrize("text", [
    "zbadaj aktualne ceny dywaników perskich",
    "przeanalizuj ten kod",
    "krok po kroku zaplanuj refaktoring",
    "przygotuj raport z ostatniej sesji",
    "zoptymalizuj ten build pod single target",
])
def test_explicit_complex_triggers(clf: ComplexityClassifier, text: str):
    assert clf.classify(text) == "complex"


def test_long_question_falls_back_to_complex(clf: ComplexityClassifier):
    text = (
        "mam taką sytuację, gram od kilku dni nową postacią ale czuję że coś jest "
        "nie tak z moim sprzętem i bez pomysłu na rozwój"
    )
    assert clf.classify(text) == "complex"


def test_short_factual_question_stays_simple(clf: ComplexityClassifier):
    assert clf.classify("Jak ma na imię nasz kot?") == "simple"


def test_two_question_words_still_complex(clf: ComplexityClassifier):
    text = "jak najlepiej zrobić to co planowałem na dziś żeby zdążyć?"
    assert clf.classify(text) == "complex"
