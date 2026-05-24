from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.config.schema import ConfigSchema, UIConfig


def test_ui_config_defaults_include_avatar_redesign_fields():
    ui = ConfigSchema().ui
    assert ui.avatar_breathing_enabled is True
    assert ui.avatar_state_poses_enabled is True
    assert ui.avatar_look_at_enabled is True
    assert ui.avatar_emotion_intensity == pytest.approx(1.25, rel=1e-6)
    assert ui.avatar_emotion_crossfade_sec == pytest.approx(0.7, rel=1e-6)


def test_ui_config_accepts_valid_custom_values():
    ui = UIConfig.model_validate(
        {
            "avatar_breathing_enabled": False,
            "avatar_state_poses_enabled": True,
            "avatar_look_at_enabled": False,
            "avatar_emotion_intensity": 2.0,
            "avatar_emotion_crossfade_sec": 1.2,
        }
    )
    assert ui.avatar_breathing_enabled is False
    assert ui.avatar_look_at_enabled is False
    assert ui.avatar_emotion_intensity == pytest.approx(2.0, rel=1e-6)
    assert ui.avatar_emotion_crossfade_sec == pytest.approx(1.2, rel=1e-6)


@pytest.mark.parametrize(
    "key,value",
    [
        ("avatar_emotion_intensity", 0.05),
        ("avatar_emotion_intensity", 3.5),
        ("avatar_emotion_crossfade_sec", 0.01),
        ("avatar_emotion_crossfade_sec", 4.5),
    ],
)
def test_ui_config_rejects_out_of_range_values(key: str, value: float):
    with pytest.raises(ValidationError):
        UIConfig.model_validate({key: value})
