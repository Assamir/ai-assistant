"""Klasyfikuje złożoność zapytania: 'simple' lub 'complex' (tryb agentowy)."""

from __future__ import annotations

import re

_COMPLEX_PATTERNS = [
    re.compile(r"zbadaj|przeanalizuj|zbierz.*informacj|przeszukaj|zbadaj temat", re.I),
    re.compile(r"sprawdź.*i.*porównaj|znajdź.*wszystk|porównaj.*i.*powiedz", re.I),
    re.compile(r"krok po kroku|zaplanuj|zrób plan|ułóż plan|zaproponuj plan", re.I),
    re.compile(r"co.*powinienem.*zrobić|jak najlepiej.*podejść|jak się przygotować", re.I),
    re.compile(r"przygotuj raport|podsumuj.*temat|zrób zestawienie|zrób przegląd", re.I),
    re.compile(r"prze?szukaj|sprawdź.*kilka|sprawdź.*wszystko", re.I),
    re.compile(r"na podstawie.*powiedz|na podstawie.*zaproponuj", re.I),
    re.compile(r"zoptymalizuj.*build|ulepsz.*build|jaki.*build.*najlepszy", re.I),
]

_SIMPLE_PATTERNS = [
    re.compile(r"^(która godzina|jaka jest godzina|co jest teraz|kiedy)[\?\.!]*$", re.I),
    re.compile(r"^(cześć|hej|dzień dobry|dobry wieczór|siemka)[\?\.!]*$", re.I),
    re.compile(r"^(tak|nie|ok|okej|dobra|spoko|rozumiem|jasne)[\?\.!]*$", re.I),
    re.compile(r"^(dziękuję|dzięki|thx)[\?\.!,]*$", re.I),
    re.compile(r"^(idź spać|obudź się|wycisz|zacznij obserwować|zatrzymaj obserwatora)", re.I),
]

MIN_WORD_COUNT = 8


class ComplexityClassifier:
    """Heurystyczny klasyfikator bez wywołania LLM."""

    def classify(self, text: str) -> str:
        stripped = text.strip()

        for pat in _SIMPLE_PATTERNS:
            if pat.search(stripped):
                return "simple"

        for pat in _COMPLEX_PATTERNS:
            if pat.search(stripped):
                return "complex"

        word_count = len(stripped.split())
        if word_count >= MIN_WORD_COUNT and ("?" in stripped or "!" in stripped):
            question_words = re.findall(r"\b(jak|gdzie|kiedy|dlaczego|co|który|która|jakie|jaką)\b", stripped, re.I)
            if len(question_words) >= 2:
                return "complex"

        return "simple"


__all__ = ["ComplexityClassifier"]
