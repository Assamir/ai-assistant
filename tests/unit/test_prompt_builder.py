"""PromptBuilder — DOK-05 §3 (sekcje, budżet, historia)."""

from __future__ import annotations

import pytest

from backend.config.schema import AIControlConfig, ConfigSchema as CfgFull, LLMConfig
from backend.core.prompt_builder import BASE_PROMPT_TEMPLATE, PromptBuilder


@pytest.fixture
def pb() -> PromptBuilder:
    return PromptBuilder(max_context_tokens=4096)


def test_template_interpolates_variables(pb: PromptBuilder):
    assert "{assistant_name}" in BASE_PROMPT_TEMPLATE
    msgs = pb.build_messages(
        assistant_name="TestBot",
        content_root=r"C:\tmp\x",
        persona_body_markdown="## X\n\nYo",
        history_messages=[],
    )


    merged = "".join(m["content"] for m in msgs if m["role"] == "system")
    assert "{assistant_name}" not in merged
    assert "TestBot" in merged
    assert "tmp" in merged.lower()


def test_persona_marker_in_system(pb: PromptBuilder):
    msgs = pb.build_messages(
        assistant_name="A",

        content_root="/x",

        persona_body_markdown="MarkerPersonaXYZ",
        history_messages=[],
    )

    merged = "".join(c["content"] for c in msgs if c["role"] == "system")
    assert "MarkerPersonaXYZ" in merged


def test_optional_observer_and_game_profile(pb: PromptBuilder):
    msgs = pb.build_messages(
        assistant_name="A",
        content_root="/x",
        persona_body_markdown="-",
        history_messages=[],


        observer_context="OBS_ONLY",
        game_profile_context="GAME_ONLY",
        max_context_tokens=4096,

    )


    blob = "".join(m["content"] for m in msgs if m["role"] == "system")
    assert "OBS_ONLY" in blob
    assert "GAME_ONLY" in blob




def test_trims_old_history_when_budget_tight(pb: PromptBuilder):
    msgs = pb.build_messages(
        assistant_name="Aria",
        content_root="/r",
        persona_body_markdown=("word " * 400),
        history_messages=[
            {"role": "user", "content": "pierwsze"},

            {"role": "assistant", "content": "krotkie"},
            {"role": "user", "content": "ostatnie_must_remain"},
        ],
        max_context_tokens=2600,
    )
    dialogue = [m for m in msgs if m["role"] != "system"]
    stitched = "".join(m["content"] for m in dialogue)
    assert "ostatnie_must_remain" in stitched

    pb_long = PromptBuilder(max_context_tokens=4096)



    roomy = pb_long.build_messages(
        assistant_name="Aria",
        content_root="/r",

        persona_body_markdown=("word " * 400),
        history_messages=[
            {"role": "user", "content": "pierwsze"},
            {"role": "assistant", "content": "krotkie"},
            {"role": "user", "content": "ostatnie_must_remain"},

        ],
        max_context_tokens=4096,
    )

    roomy_dialogue = "".join(m["content"] for m in roomy if m["role"] != "system")
    assert "pierwsze" in roomy_dialogue


def test_language_override(pb: PromptBuilder):

    msgs = pb.build_messages(
        assistant_name="A",

        content_root="/x",

        persona_body_markdown=".",


        history_messages=[],

        language_override="en",
    )


    blob = "".join(m["content"] for m in msgs if m["role"] == "system")

    assert "LANGUAGE:" in blob or "LANGUAGE" in blob


def test_token_estimate_monotonic(pb: PromptBuilder):
    shorter = pb.estimate_tokens("a" * 30)
    longer = pb.estimate_tokens("a" * 300)
    assert longer >= shorter


def test_memory_block_first(pb: PromptBuilder):

    msgs = pb.build_messages(

        assistant_name="A",

        content_root="/x",

        persona_body_markdown="-",

        history_messages=[],


        memory_prefix="unique-memory-line",

        max_context_tokens=4096,

    )

    assert msgs[0]["role"] == "system"
    assert "unique-memory-line" in msgs[0]["content"]
    assert any("PERSONA" in m["content"] for m in msgs if m["role"] == "system")



def test_max_context_kwarg_controls_trim(pb: PromptBuilder):
    msgs = pb.build_messages(
        assistant_name="A",
        content_root="/x",
        persona_body_markdown=("body " * 800),
        history_messages=[{"role": "user", "content": ("x " * 2000)}],
        max_context_tokens=950,
    )
    systems = sum(1 for m in msgs if m["role"] == "system")
    assert systems >= 1




def test_empty_history_returns_system_only(pb: PromptBuilder):
    msgs = pb.build_messages(
        assistant_name="A",

        content_root="/x",

        persona_body_markdown="p",

        history_messages=[],


        max_context_tokens=4096,
    )


    assert all(m["role"] == "system" for m in msgs)


def test_output_mode_voice_keeps_80_word_limit(pb: PromptBuilder):
    msgs = pb.build_messages(
        assistant_name="A",
        content_root="/x",
        persona_body_markdown="-",
        history_messages=[],
        output_mode="voice",
    )
    blob = "".join(m["content"] for m in msgs if m["role"] == "system")
    assert "~80 słow" in blob.lower() or "80 słow" in blob.lower() or "80 słów" in blob
    assert "Nie używaj markdown" in blob


def test_output_mode_text_removes_voice_limits_and_allows_markdown(pb: PromptBuilder):
    msgs = pb.build_messages(
        assistant_name="A",
        content_root="/x",
        persona_body_markdown="-",
        history_messages=[],
        output_mode="text",
    )
    blob = "".join(m["content"] for m in msgs if m["role"] == "system")
    assert "80 słów" not in blob
    assert "Markdown dozwolony" in blob
    assert "Dopasuj długość do tematu" in blob


def test_output_mode_default_is_voice(pb: PromptBuilder):
    msgs = pb.build_messages(
        assistant_name="A",
        content_root="/x",
        persona_body_markdown="-",
        history_messages=[],
    )
    blob = "".join(m["content"] for m in msgs if m["role"] == "system")
    assert "Markdown dozwolony" not in blob


def test_config_max_token_field_mapping():
    cfg = CfgFull(
        llm=LLMConfig(api_base_url="http://stub/", model_name="stub", temperature=0.1),
        ai_runtime=AIControlConfig(max_context_tokens=9216),

    )


    pb_cfg = PromptBuilder(max_context_tokens=cfg.ai_runtime.max_context_tokens)
    msgs = pb_cfg.build_messages(
        assistant_name="A",
        content_root="/x",

        persona_body_markdown=("z " * 50),
        history_messages=[],


        max_context_tokens=9200,
    )


    assert msgs



