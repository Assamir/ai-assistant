from backend.core.tts_streaming import sentence_split, strip_markdown_for_tts


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


# --- strip_markdown_for_tts -------------------------------------------------


def test_strip_md_empty():
    assert strip_markdown_for_tts("") == ""
    assert strip_markdown_for_tts("   ") == ""


def test_strip_md_bold_stars():
    assert strip_markdown_for_tts("To **mocny** build") == "To mocny build"


def test_strip_md_bold_underscores():
    assert strip_markdown_for_tts("To __mocny__ build") == "To mocny build"


def test_strip_md_italic_stars():
    assert strip_markdown_for_tts("To *świetny* pomysł") == "To świetny pomysł"


def test_strip_md_link_keeps_label():
    text = "Sprawdź [poradnik tutaj](https://example.com/x)"
    out = strip_markdown_for_tts(text)
    assert "poradnik tutaj" in out
    assert "https" not in out
    assert "[" not in out and "]" not in out


def test_strip_md_bare_url_removed():
    out = strip_markdown_for_tts("Wejdź na https://mobalytics.gg/poe-2 by więcej.")
    assert "https" not in out
    assert "mobalytics" not in out
    assert "Wejdź na" in out


def test_strip_md_headings():
    out = strip_markdown_for_tts("## Najlepsze buildy\nLista tutaj")
    assert out.startswith("Najlepsze buildy")


def test_strip_md_bullets():
    text = "- pierwszy\n- drugi\n- trzeci"
    out = strip_markdown_for_tts(text)
    assert "-" not in out
    assert "pierwszy" in out and "drugi" in out and "trzeci" in out


def test_strip_md_numbered_list_kept():
    """Numerowane listy zostawiamy — '1. X' brzmi naturalnie."""
    text = "1. Flicker Strike\n2. Lightning Spear"
    out = strip_markdown_for_tts(text)
    assert "1." in out
    assert "2." in out


def test_strip_md_code_inline_keeps_content():
    assert strip_markdown_for_tts("Użyj `web_search` żeby sprawdzić") == "Użyj web_search żeby sprawdzić"


def test_strip_md_code_fence_removed():
    text = "Przed.\n```\nkod do usunięcia\n```\nPo."
    out = strip_markdown_for_tts(text)
    assert "kod do usunięcia" not in out
    assert "Przed" in out and "Po" in out


def test_strip_md_real_world_qwen_response():
    """Dokładny fragment z odpowiedzi qwen2.5-14b o PoE2 buildach."""
    text = (
        "Najnowsze informacje pokazują kilka mocnych buildów:\n\n"
        "1. **Flicker Strike Slayer** — Postać oparta na teleportacjach.\n"
        "2. **Lightning Spear Amazon** — Szybka i uniwersalna.\n\n"
        "Odwiedź [poebuilds.cc](https://www.poebuilds.cc/) po więcej."
    )
    out = strip_markdown_for_tts(text)
    assert "**" not in out
    assert "[" not in out
    assert "https" not in out
    assert "Flicker Strike Slayer" in out
    assert "Lightning Spear Amazon" in out
    assert "poebuilds.cc" in out  # label linku zachowany


def test_strip_md_double_newline_becomes_period():
    text = "Pierwszy akapit.\n\nDrugi akapit."
    out = strip_markdown_for_tts(text)
    # Pomiędzy musi być kropka jako pauza TTS
    assert "akapit. Drugi" in out or "akapit.Drugi" in out


def test_strip_md_pipeline_into_sentence_split():
    """Smoke test: strip + sentence_split razem nie gubi treści."""
    text = "**Pierwszy** build to *Flicker*. Drugi to **Lightning**. Trzeci to **Cold**."
    sentences = sentence_split(strip_markdown_for_tts(text))
    joined = " ".join(sentences)
    assert "Flicker" in joined
    assert "Lightning" in joined
    assert "Cold" in joined
    assert "**" not in joined
