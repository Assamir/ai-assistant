"""Sandbox audit — weryfikacja że SandboxValidator blokuje path traversal i złe URL."""

from __future__ import annotations

import pytest

from backend.mcp.sandbox import OfflineModeError, SandboxValidator, SandboxViolation


@pytest.fixture
def sv(tmp_path):
    return SandboxValidator(str(tmp_path))


# ─── Path validation ──────────────────────────────────────────────────────────


def test_path_inside_root_allowed(sv, tmp_path):
    p = sv.validate_path("docs/readme.txt")
    assert str(p).startswith(str(tmp_path))


def test_path_traversal_blocked(sv):
    with pytest.raises(SandboxViolation):
        sv.validate_path("../../etc/passwd")


def test_path_absolute_outside_blocked(sv, tmp_path):
    outside = str(tmp_path.parent / "secret.txt")
    with pytest.raises(SandboxViolation):
        sv.validate_path(outside)


def test_path_dotdot_in_middle_blocked(sv):
    with pytest.raises(SandboxViolation):
        sv.validate_path("docs/../../../windows/system32")


def test_path_nested_inside_allowed(sv, tmp_path):
    p = sv.validate_path("knowledge/daily_checks/note.md")
    assert str(p).startswith(str(tmp_path))


# ─── URL validation ───────────────────────────────────────────────────────────


def test_http_url_allowed(sv):
    assert sv.validate_url("http://example.com") == "http://example.com"


def test_https_url_allowed(sv):
    assert sv.validate_url("https://duckduckgo.com/?q=poe2") == "https://duckduckgo.com/?q=poe2"


def test_file_url_blocked(sv):
    with pytest.raises(SandboxViolation):
        sv.validate_url("file:///etc/passwd")


def test_javascript_url_blocked(sv):
    with pytest.raises(SandboxViolation):
        sv.validate_url("javascript:alert(1)")


def test_empty_url_blocked(sv):
    with pytest.raises(SandboxViolation):
        sv.validate_url("")


def test_ftp_url_blocked(sv):
    with pytest.raises(SandboxViolation):
        sv.validate_url("ftp://files.example.com/archive.zip")


# ─── Online mode ──────────────────────────────────────────────────────────────


def test_online_mode_passes(sv):
    sv.check_online_mode({"online": True})  # no raise


def test_offline_mode_raises(sv):
    with pytest.raises(OfflineModeError):
        sv.check_online_mode({"online": False})


def test_missing_online_key_defaults_to_online(sv):
    sv.check_online_mode({})  # default True — no raise
