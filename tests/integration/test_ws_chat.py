"""WebSocket — chat_text, PTT, audio_duck (Starlette TestClient, sync)."""

from __future__ import annotations

import base64
import io
import json
import wave
from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient

from backend.core.command_handlers import CommandExecutionResult
from backend.core.interfaces import BaseSTTEngine
from backend.main import app


# ─── Pomocnicze ──────────────────────────────────────────────────────────────


def _wav(frames: int = 320) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * frames)
    return buf.getvalue()


def _recv(ws, n: int) -> list[dict]:
    return [json.loads(ws.receive_text()) for _ in range(n)]


class _MockSTT(BaseSTTEngine):
    def __init__(self, text: str = "cześć") -> None:
        self._text = text

    async def transcribe(self, audio_data: bytes) -> str:
        return self._text

    async def get_confidence(self, audio_data: bytes) -> float:
        return 0.95


# ─── Testy podstawowych zdarzeń ───────────────────────────────────────────────


def test_initial_system_state_contains_session_id():
    """Po połączeniu serwer wysyła system_state z session_id i health=ok."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            msg = json.loads(ws.receive_text())
    assert msg["event"] == "system_state"
    assert "session_id" in msg["payload"]
    assert msg["payload"]["health"] == "ok"


def test_frontend_ready_replies_health_ready():
    """frontend_ready → system_state {health: ready}."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()  # initial system_state
            ws.send_json({"event": "frontend_ready", "payload": {}})
            msg = json.loads(ws.receive_text())
    assert msg["event"] == "system_state"
    assert msg["payload"]["health"] == "ready"


def test_audio_duck_echoes_params():
    """audio_duck → odbicie target_volume i ramp_ms + visual_state=listening."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()
            ws.send_json({"event": "audio_duck", "payload": {"target_volume": 0.4, "ramp_ms": 250}})
            events = _recv(ws, 2)
    duck = next(e for e in events if e["event"] == "audio_duck")
    vs = next(e for e in events if e["event"] == "visual_state")
    assert duck["payload"]["target_volume"] == pytest.approx(0.4)
    assert duck["payload"]["ramp_ms"] == 250
    assert vs["payload"]["state"] == "listening"


def test_ptt_start_ducks_and_listens():
    """ptt_start → audio_duck (vol=0) + visual_state=listening."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()
            ws.send_json({"event": "ptt_start", "payload": {"ramp_ms": 80}})
            events = _recv(ws, 2)
    duck = next(e for e in events if e["event"] == "audio_duck")
    vs = next(e for e in events if e["event"] == "visual_state")
    assert duck["payload"]["target_volume"] == pytest.approx(0.0)
    assert duck["payload"]["ramp_ms"] == 80
    assert vs["payload"]["state"] == "listening"


# ─── chat_text ───────────────────────────────────────────────────────────────


def test_chat_text_returns_emotion_and_text_overlay():
    """chat_text → visual_state(thinking), emotion, text_overlay, visual_state(idle)."""
    fake = CommandExecutionResult(success=True, message="Witaj!", emotion="happy")
    with TestClient(app) as client:
        ctx = app.state.ctx
        ctx.tts_engine = None
        with patch.object(ctx.orchestrator, "handle_user_message", new=AsyncMock(return_value=fake)):
            with client.websocket_connect("/ws") as ws:
                ws.receive_text()
                ws.send_json({"event": "chat_text", "payload": {"text": "Cześć!"}})
                events = _recv(ws, 4)

    names = [e["event"] for e in events]
    assert names[0] == "visual_state"
    assert events[0]["payload"]["state"] == "thinking"
    assert "emotion" in names
    assert "text_overlay" in names
    assert names[-1] == "visual_state"
    assert events[-1]["payload"]["state"] == "idle"


def test_chat_text_emotion_matches_verdict():
    """Emocja w zdarzeniu WS odpowiada emotion z CommandExecutionResult."""
    fake = CommandExecutionResult(success=True, message="Super!", emotion="excited")
    with TestClient(app) as client:
        ctx = app.state.ctx
        ctx.tts_engine = None
        with patch.object(ctx.orchestrator, "handle_user_message", new=AsyncMock(return_value=fake)):
            with client.websocket_connect("/ws") as ws:
                ws.receive_text()
                ws.send_json({"event": "chat_text", "payload": {"text": "Jak leci?"}})
                events = _recv(ws, 4)

    emo_evt = next(e for e in events if e["event"] == "emotion")
    assert emo_evt["payload"]["emotion"] == "excited"


def test_chat_text_empty_does_not_call_orchestrator():
    """chat_text z pustym tekstem → orchestrator nie wywoływany."""
    mock_hum = AsyncMock()
    with TestClient(app) as client:
        ctx = app.state.ctx
        with patch.object(ctx.orchestrator, "handle_user_message", new=mock_hum):
            with client.websocket_connect("/ws") as ws:
                ws.receive_text()
                ws.send_json({"event": "chat_text", "payload": {"text": "   "}})
                # potwierdzamy że nic więcej nie czeka — ping/pong
                ws.send_json({"event": "ping"})
                pong = json.loads(ws.receive_text())
                assert pong["event"] == "pong"

    assert mock_hum.call_count == 0


def test_chat_text_appends_to_conversation():
    """Po chat_text wiadomości user i assistant są w ConversationStore."""
    fake = CommandExecutionResult(success=True, message="Rozumiem.", emotion="neutral")
    sid_holder: list[str] = []

    with TestClient(app) as client:
        ctx = app.state.ctx
        ctx.tts_engine = None
        with patch.object(ctx.orchestrator, "handle_user_message", new=AsyncMock(return_value=fake)):
            with client.websocket_connect("/ws") as ws:
                init = json.loads(ws.receive_text())
                sid_holder.append(init["payload"]["session_id"])
                ws.send_json({"event": "chat_text", "payload": {"text": "Hej!"}})
                _recv(ws, 4)

    sid = sid_holder[0]
    hist = ctx.conversation.tail(sid)
    roles = [m["role"] for m in hist]
    assert "user" in roles
    assert "assistant" in roles


# ─── PTT end ─────────────────────────────────────────────────────────────────


def test_ptt_end_with_audio_sends_reply():
    """ptt_end + base64 audio → STT → emotion + text_overlay."""
    fake = CommandExecutionResult(success=True, message="Słyszę cię!", emotion="neutral")
    audio_b64 = base64.standard_b64encode(_wav()).decode()

    with TestClient(app) as client:
        ctx = app.state.ctx
        ctx.stt_engine = _MockSTT("hej asystencie")
        ctx.tts_engine = None
        with patch.object(ctx.orchestrator, "handle_user_message", new=AsyncMock(return_value=fake)):
            with client.websocket_connect("/ws") as ws:
                ws.receive_text()
                ws.send_json({"event": "ptt_end", "payload": {"audio": audio_b64}})
                # visual_state(thinking), audio_duck, emotion, text_overlay, visual_state(idle)
                events = _recv(ws, 5)

    names = [e["event"] for e in events]
    assert "emotion" in names
    assert "text_overlay" in names
    to = next(e for e in events if e["event"] == "text_overlay")
    assert to["payload"]["text"] == "Słyszę cię!"


def test_ptt_end_without_audio_skips_reply():
    """ptt_end bez pola audio → orchestrator nie wywoływany, 3 zdarzenia."""
    mock_hum = AsyncMock()
    with TestClient(app) as client:
        ctx = app.state.ctx
        ctx.stt_engine = _MockSTT()
        with patch.object(ctx.orchestrator, "handle_user_message", new=mock_hum):
            with client.websocket_connect("/ws") as ws:
                ws.receive_text()
                ws.send_json({"event": "ptt_end", "payload": {}})
                # visual_state(thinking), audio_duck, visual_state(idle) — bez process_text
                events = _recv(ws, 3)

    assert mock_hum.call_count == 0
    names = {e["event"] for e in events}
    assert "visual_state" in names
    assert "audio_duck" in names


def test_ptt_end_unwinds_volume_to_1():
    """ptt_end → audio_duck.target_volume == 1.0 (odwrócenie duck)."""
    fake = CommandExecutionResult(success=True, message="OK", emotion="neutral")
    audio_b64 = base64.standard_b64encode(_wav()).decode()

    with TestClient(app) as client:
        ctx = app.state.ctx
        ctx.stt_engine = _MockSTT("test")
        ctx.tts_engine = None
        with patch.object(ctx.orchestrator, "handle_user_message", new=AsyncMock(return_value=fake)):
            with client.websocket_connect("/ws") as ws:
                ws.receive_text()
                ws.send_json({"event": "ptt_end", "payload": {"audio": audio_b64, "ramp_ms": 120}})
                events = _recv(ws, 5)

    duck = next(e for e in events if e["event"] == "audio_duck")
    assert duck["payload"]["target_volume"] == pytest.approx(1.0)
    assert duck["payload"]["ramp_ms"] == 120
