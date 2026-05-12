"""Female / male pronouns w systemowym promptcie — sterowane przez tts.voice_gender."""

from __future__ import annotations

from backend.core.prompt_builder import PromptBuilder, detect_voice_gender


def test_detect_voice_gender_female_gosia():
    p = "C:/code/.../piper-voices/pl/pl_PL/gosia/medium/pl_PL-gosia-medium.onnx"
    assert detect_voice_gender(p) == "female"


def test_detect_voice_gender_female_mai():
    assert detect_voice_gender("tts_models/pl_PL/mai_female") == "female"


def test_detect_voice_gender_male_darkman():
    assert detect_voice_gender("piper-voices/pl/pl_PL/darkman/medium/pl_PL-darkman-medium.onnx") == "male"


def test_detect_voice_gender_male_bass():
    assert detect_voice_gender("piper-voices/pl/pl_PL/bass/high/pl_PL-bass-high.onnx") == "male"


def test_detect_voice_gender_neutral_when_unknown():
    assert detect_voice_gender("piper-voices/pl/pl_PL/mls_6892/low/pl_PL-mls_6892-low.onnx") == "neutral"
    assert detect_voice_gender(None) == "neutral"
    assert detect_voice_gender("") == "neutral"


def test_build_messages_injects_female_gender_section():
    pb = PromptBuilder(max_context_tokens=4096)
    msgs = pb.build_messages(
        assistant_name="Aria",
        content_root=".",
        persona_body_markdown="## Osobowość\n\nTest",
        history_messages=[],
        voice_gender="female",
    )
    system_prompt = next(m["content"] for m in msgs if m["role"] == "system")
    assert "RODZAJ GRAMATYCZNY" in system_prompt
    assert "rodzaju żeńskim" in system_prompt
    assert "zrobiłam" in system_prompt


def test_build_messages_injects_male_gender_section():
    pb = PromptBuilder(max_context_tokens=4096)
    msgs = pb.build_messages(
        assistant_name="Aria",
        content_root=".",
        persona_body_markdown="## Osobowość\n\nTest",
        history_messages=[],
        voice_gender="male",
    )
    system_prompt = next(m["content"] for m in msgs if m["role"] == "system")
    assert "rodzaju męskim" in system_prompt
    assert "zrobiłem" in system_prompt


def test_build_messages_neutral_omits_section():
    pb = PromptBuilder(max_context_tokens=4096)
    msgs = pb.build_messages(
        assistant_name="Aria",
        content_root=".",
        persona_body_markdown="## Osobowość\n\nTest",
        history_messages=[],
        voice_gender="neutral",
    )
    system_prompt = next(m["content"] for m in msgs if m["role"] == "system")
    assert "RODZAJ GRAMATYCZNY" not in system_prompt
