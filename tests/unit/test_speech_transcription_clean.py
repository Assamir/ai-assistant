from backend.services.speech_transcription_clean import strip_wake_prefixes


def test_strip_wake_prefix_basic():
    assert strip_wake_prefixes("Hej Aria, co słychać?", ["hej aria"]) == "co słychać?"


def test_strip_longest_prefix_first():
    assert strip_wake_prefixes("Hej Aria jest super", ["hej", "hej aria"]) == "jest super"


def test_strip_no_match():
    assert strip_wake_prefixes("Kim jest Tez", ["hej aria"]) == "Kim jest Tez"
