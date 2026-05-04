"""resolve_default_emotion — DOK-06 §9."""

from __future__ import annotations

import pytest

from backend.core.emotion_parser import parse_emotion_tag, resolve_default_emotion




def test_parse_emotion():

    emotion, remainder = parse_emotion_tag("[EMO:happy] Cześć!")


    assert emotion == "happy"

    assert remainder == "Cześć!"





def test_unknown_emotion():

    emotion, remainder = parse_emotion_tag("[EMO:x_y] tekst")


    assert emotion == "neutral"

    assert remainder == "tekst"




def test_no_tag():



    emotion, remainder = parse_emotion_tag("plain")





    assert emotion == "neutral"



    assert remainder == "plain"




@pytest.mark.parametrize(
    "parsed,bias,state,expect",
    [

        (None, "happy", "healthy", "happy"),

        ("excited", "sad", "healthy", "excited"),

        (None, "happy", "error", "sad"),

        (None, "", "healthy", "neutral"),

    ],

)


def test_resolve_priority(parsed, bias, state, expect):


    assert resolve_default_emotion(parsed, bias, state) == expect
