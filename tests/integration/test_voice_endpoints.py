"""Testy HTTP: voice endpoints z mockowanymi STT/TTS (bez GPU/mikrofonu)."""

from __future__ import annotations

import io
import json
import wave
from typing import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from pathlib import Path
from httpx import ASGITransport, AsyncClient

from backend.core.command_handlers import CommandExecutionResult
from backend.core.interfaces import BaseSTTEngine, BaseTTSEngine
from backend.core.orchestrator import ConversationOrchestrator
from backend.db.migration_runner import MigrationRunner
from backend.mcp.registry import build_default_tool_registry
from backend.main import app
from backend.services.player_profile import PlayerProfileRepository


# ─── Pomocnicze ──────────────────────────────────────────────────────────────


def _make_wav(sample_rate: int = 16000, frames: int = 320) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * frames)
    return buf.getvalue()


class _MockSTT(BaseSTTEngine):
    def __init__(self, text: str = "co słychać", confidence: float = 0.9) -> None:
        self._text = text
        self._conf = confidence

    async def transcribe(self, audio_data: bytes) -> str:
        return self._text

    async def get_confidence(self, audio_data: bytes) -> float:
        return self._conf


class _MockTTS(BaseTTSEngine):
    async def speak(self, text: str, emotion=None) -> bytes:
        return _make_wav()

    async def stream_to_tts(self, text: str) -> AsyncIterator[bytes]:  # type: ignore[override]
        yield _make_wav()


# ─── Fixture ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def voice_client(tmp_path: Path):
    """AsyncClient z mockowanymi STT i TTS wstrzykniętymi do app.state.ctx."""
    from backend.api.app_context import create_app_context
    from pathlib import Path as Pth

    db_path = str(tmp_path / "voice_http.db")
    MigrationRunner(db_path).run_migrations()

    ctx = create_app_context()
    root = Pth(ctx.config.general.content_root).expanduser()
    ctx.db_path = db_path
    ctx.tool_registry = build_default_tool_registry(
        db_path=db_path,
        mcp_cfg=ctx.config.mcp,
        content_root=str(root.resolve()),
    )
    ctx.player_profile_store = PlayerProfileRepository(
        str((root / "data" / "player_profile.yaml").resolve()),
        db_path,
    )
    pers = ctx.orchestrator.state.get("active_persona", "default")
    if not isinstance(pers, str):
        pers = "default"
    ctx.orchestrator = ConversationOrchestrator(
        configuration=ctx.config,
        lm_client=ctx.llm_client,
        prompt_builder=ctx.prompt_builder,
        persona_loader=ctx.persona_loader,
        command_matcher=ctx.command_matcher,
        tool_registry=ctx.tool_registry,
        active_persona=pers,
        emitter=None,
        db_path=db_path,
        semantic_recall=ctx.semantic_recall,
        player_profile_repo=ctx.player_profile_store,
    )
    from backend.mcp.context_tools import register_context_dependent_mcp_tools

    register_context_dependent_mcp_tools(ctx)
    ctx.stt_engine = _MockSTT()
    ctx.tts_engine = _MockTTS()
    app.state.ctx = ctx
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, ctx
    try:
        await ctx.llm_client.aclose()
    finally:
        app.state.ctx = None


# ─── /voice/transcribe ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transcribe_200_with_mock_stt(voice_client):
    """POST /voice/transcribe z WAV → 200 + text + confidence."""
    ac, _ = voice_client
    r = await ac.post(
        "/api/v1/voice/transcribe",
        files={"audio": ("t.wav", _make_wav(), "audio/wav")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "co słychać"
    assert "confidence" in body
    assert body["action_hint"] in {"process", "confirm", "reject"}


@pytest.mark.asyncio
async def test_transcribe_high_confidence_hint_process(voice_client):
    """Pewność 0.9 (≥ 0.7) → action_hint == 'process'."""
    ac, ctx = voice_client
    ctx.stt_engine = _MockSTT(confidence=0.9)
    r = await ac.post(
        "/api/v1/voice/transcribe",
        files={"audio": ("t.wav", _make_wav(), "audio/wav")},
    )
    assert r.json()["action_hint"] == "process"


@pytest.mark.asyncio
async def test_transcribe_medium_confidence_hint_confirm(voice_client):
    """Pewność 0.6 (0.45 ≤ conf < 0.7) → action_hint == 'confirm'."""
    ac, ctx = voice_client
    ctx.stt_engine = _MockSTT(confidence=0.6)
    r = await ac.post(
        "/api/v1/voice/transcribe",
        files={"audio": ("t.wav", _make_wav(), "audio/wav")},
    )
    assert r.json()["action_hint"] == "confirm"


@pytest.mark.asyncio
async def test_transcribe_low_confidence_hint_reject(voice_client):
    """Pewność 0.3 (< floor 0.45) → action_hint == 'reject'."""
    ac, ctx = voice_client
    ctx.stt_engine = _MockSTT(confidence=0.3)
    r = await ac.post(
        "/api/v1/voice/transcribe",
        files={"audio": ("t.wav", _make_wav(), "audio/wav")},
    )
    assert r.json()["action_hint"] == "reject"


@pytest.mark.asyncio
async def test_transcribe_503_without_stt(voice_client):
    """Brak STT engine → 503."""
    ac, ctx = voice_client
    ctx.stt_engine = None
    r = await ac.post(
        "/api/v1/voice/transcribe",
        files={"audio": ("t.wav", _make_wav(), "audio/wav")},
    )
    assert r.status_code == 503


# ─── /voice/synthesize ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_synthesize_returns_wav_bytes(voice_client):
    """POST /voice/synthesize → 200 audio/wav z zawartością."""
    ac, _ = voice_client
    r = await ac.post(
        "/api/v1/voice/synthesize",
        json={"text": "Cześć!", "emotion": "happy"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
    assert len(r.content) > 0


@pytest.mark.asyncio
async def test_synthesize_accepts_different_emotions(voice_client):
    """Różne emocje (excited, sad, neutral) → zawsze 200."""
    ac, _ = voice_client
    for emotion in ("excited", "sad", "neutral", "thinking"):
        r = await ac.post(
            "/api/v1/voice/synthesize",
            json={"text": "Test.", "emotion": emotion},
        )
        assert r.status_code == 200, f"emotion={emotion!r} failed"


@pytest.mark.asyncio
async def test_synthesize_503_without_tts(voice_client):
    """Brak TTS engine → 503."""
    ac, ctx = voice_client
    ctx.tts_engine = None
    r = await ac.post(
        "/api/v1/voice/synthesize",
        json={"text": "Test.", "emotion": "neutral"},
    )
    assert r.status_code == 503


# ─── /voice/process ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_voice_process_full_pipeline(voice_client):
    """POST /voice/process: STT → chat → TTS → 200 WAV + X-Emotion header."""
    ac, ctx = voice_client
    fake = CommandExecutionResult(success=True, message="OK!", emotion="excited")
    with patch.object(ctx.orchestrator, "handle_user_message", new=AsyncMock(return_value=fake)):
        r = await ac.post(
            "/api/v1/voice/process",
            files={"audio": ("test.wav", _make_wav(), "audio/wav")},
        )
    assert r.status_code == 200
    assert r.headers.get("x-emotion") == "excited"
    assert r.headers["content-type"] == "audio/wav"
    assert len(r.content) > 0


@pytest.mark.asyncio
async def test_voice_process_503_without_stt(voice_client):
    """Brak STT engine w /voice/process → 503."""
    ac, ctx = voice_client
    ctx.stt_engine = None
    r = await ac.post(
        "/api/v1/voice/process",
        files={"audio": ("test.wav", _make_wav(), "audio/wav")},
    )
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_voice_process_503_without_tts(voice_client):
    """Brak TTS engine w /voice/process → 503 po STT."""
    ac, ctx = voice_client
    ctx.tts_engine = None
    fake = CommandExecutionResult(success=True, message="Hej!", emotion="neutral")
    with patch.object(ctx.orchestrator, "handle_user_message", new=AsyncMock(return_value=fake)):
        r = await ac.post(
            "/api/v1/voice/process",
            files={"audio": ("test.wav", _make_wav(), "audio/wav")},
        )
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_voice_process_with_session_metadata(voice_client):
    """POST /voice/process z metadata JSON → session_id przekazany do konwersacji."""
    ac, ctx = voice_client
    import json as _json
    meta = _json.dumps({"session_id": "test-sess-42"})
    fake = CommandExecutionResult(success=True, message="Tak!", emotion="neutral")
    with patch.object(ctx.orchestrator, "handle_user_message", new=AsyncMock(return_value=fake)):
        r = await ac.post(
            "/api/v1/voice/process",
            files={"audio": ("test.wav", _make_wav(), "audio/wav")},
            data={"metadata": meta},
        )
    assert r.status_code == 200
    hist = ctx.conversation.tail("test-sess-42")
    assert any(m["role"] == "user" for m in hist)
