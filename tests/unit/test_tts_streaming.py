from backend.core.tts_streaming import sentence_split


def test_empty_returns_empty():
    assert sentence_split("") == []
    assert sentence_split("   ") == []


def test_single_sentence_no_split():
    result = sentence_split("To jest jedno zdanie bez końca")
    assert result == ["To jest jedno zdanie bez końca"]


def test_splits_on_period():
    result = sentence_split(
        "Pierwsze zdanie zawiera ważne informacje o buildzie. "
        "Drugie zdanie jest tutaj dłuższe niż wymagane minimum znaków."
    )
    assert len(result) == 2
    assert result[0].endswith(".")
    assert "Drugie" in result[1]


def test_splits_on_exclamation():
    result = sentence_split(
        "Uwaga, masz rzadki drop który możesz sprzedać za dużo walety! "
        "To jest bardzo ważna informacja dla twojego postępu w grze."
    )
    assert len(result) == 2
    assert result[0].endswith("!")


def test_splits_on_question():
    result = sentence_split(
        "Co widzisz na tym ekranie, to jest ciekawy przedmiot? "
        "To jest przedmiot z bardzo wysokim tier który warto sprawdzić."
    )
    assert len(result) == 2


def test_abbrev_np_not_split():
    text = "Graj np. Deadeye lub Ranger, bo są najsilniejsze w tym sezonie."
    result = sentence_split(text)
    assert len(result) == 1


def test_abbrev_itd_not_split():
    text = "Zbierasz złoto, potiony, itd. To da ci przewagę w późnej grze."
    result = sentence_split(text)
    assert len(result) == 1


def test_short_segment_merged():
    # "Tak!" is shorter than min_len=30 → merged with next
    result = sentence_split("Tak! To jest bardzo ważna informacja, którą powinieneś zapamiętać na przyszłość.")
    assert len(result) == 1


def test_three_sentences():
    text = (
        "Zdobyłeś rzadki przedmiot, który warto sprawdzić. "
        "To może być Exalted Orb lub coś cenniejszego. "
        "Koniecznie zajrzyj do ekwipunku i sprawdź wartość."
    )
    result = sentence_split(text)
    assert len(result) >= 2


def test_no_split_without_whitespace():
    # "end.start" — no whitespace after dot → should not split
    result = sentence_split("Wersja3.14jest teraz dostępna dla wszystkich graczy na świecie.")
    assert len(result) == 1


def test_preserves_text_content():
    text = "Pierwsze zdanie zawiera ważne informacje. Drugie zdanie też ma sens i jest dłuższe."
    joined = " ".join(sentence_split(text))
    # All words should be preserved
    assert "ważne" in joined
    assert "długie" not in joined  # sanity check — we didn't add anything
