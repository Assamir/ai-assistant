"""WebSocket `/ws` — multiplexowany kanał `{event,payload}` (api-plan)."""

from __future__ import annotations

import asyncio
import base64
import json as _json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError

from backend.api.app_context import ensure_ws_db_session
from backend.core.orchestrator import OrchestratorState

_logger = logging.getLogger(__name__)


class _WsFrame(BaseModel):

    event: str
    payload: dict[str, Any] = {}


def _int_ms(raw: Any, *, default: int = 160) -> int:
    try:
        v = int(float(raw))

    except (TypeError, ValueError):
        return default

    return v if v > 0 else default


async def websocket_endpoint(ws: WebSocket, app) -> None:


    ctx = getattr(app.state, "ctx", None)

    if ctx is None:


        await ws.close(code=1011)
        return


    await ws.accept()


    mgr = ctx.websocket_manager
    sid = mgr.bind(ws)


    async def emitter(name: str, payload: dict) -> None:
        await mgr.send_to_session(sid, name, payload)
        if name == "mcp_cache_invalidate_all":
            from backend.db.repositories import MCPCacheRepository

            await MCPCacheRepository(ctx.db_path).invalidate_all()
        if name in ("observer_start", "observer_stop"):
            from backend.services.game_detection_tracking import sync_game_detections_on_observer_command

            await sync_game_detections_on_observer_command(ctx, name)
        if name == "backup_request":
            from pathlib import Path as _Path
            from backend.services.backup_service import run_backup as _run_backup

            _root = _Path(ctx.config.general.content_root).expanduser()

            async def _bcast(ev: str, pl: dict) -> None:
                for _sid in ctx.websocket_manager.iter_session_ids():
                    await ctx.websocket_manager.send_to_session(_sid, ev, pl)

            asyncio.create_task(_run_backup(_root, broadcast_fn=_bcast))
        if name == "reload_config":
            _cfg_path = getattr(ctx, "resolved_config_path", None)
            if _cfg_path:
                try:
                    from backend.config.loader import ConfigLoader as _CL
                    from backend.services.runtime_config import apply_reload_configuration as _arc
                    from backend.services.config_hot_reload import _broadcast_reload as _br
                    _new_cfg = _CL().load_config(_cfg_path)
                    await _arc(ctx, _new_cfg)
                    await _br(ctx, "config")
                except Exception as _exc:
                    _logger.warning("Manual reload_config failed: %s", _exc)
        if name == "open_documents":
            import subprocess as _sp
            import sys as _sys
            from pathlib import Path as _Path
            _docs = _Path(ctx.config.general.content_root).expanduser() / "documents"
            _docs.mkdir(parents=True, exist_ok=True)
            try:
                if _sys.platform == "win32":
                    _sp.Popen(["explorer", str(_docs)], shell=False)
                elif _sys.platform == "darwin":
                    _sp.Popen(["open", str(_docs)])
                else:
                    _sp.Popen(["xdg-open", str(_docs)])
            except Exception as _exc:
                _logger.warning("open_documents failed: %s", _exc)


    async def emit_chunks(text_body: str, emotion: str) -> None:
        from backend.core.quiet_hours import quiet_hours_suppresses_voice
        from backend.core.tts_streaming import sentence_split

        synth = getattr(ctx, "tts_engine", None)
        trimmed = text_body.strip()
        if trimmed:
            await mgr.send_to_session(sid, "assistant_reply_text", {"text": trimmed})

        qh = quiet_hours_suppresses_voice(ctx.config)
        if trimmed and qh:
            await mgr.send_to_session(sid, "text_overlay", {"text": trimmed})
            return

        if trimmed and synth is not None:
            stride = max(512, getattr(ctx.config.tts, "chunk_bytes", 4096))
            any_audio = False
            for sentence in sentence_split(trimmed):
                try:
                    wav = await synth.speak(sentence, emotion=emotion or None)
                except Exception:
                    _logger.warning("TTS speak failed for sentence", exc_info=True)
                    wav = b""
                if wav:
                    any_audio = True
                    blob = base64.standard_b64encode(wav).decode("ascii")
                    for offset in range(0, len(blob), stride):
                        await mgr.send_to_session(
                            sid,
                            "audio_stream",
                            {"chunk_base64": blob[offset : offset + stride]},
                        )
            if not any_audio:
                await mgr.send_to_session(sid, "text_overlay", {"text": trimmed})
        elif trimmed:
            await mgr.send_to_session(sid, "text_overlay", {"text": trimmed})

    async def process_text(user_text: str) -> None:
        hist = ctx.conversation.tail(sid)

        db_id = await ensure_ws_db_session(ctx, sid)
        try:
            from backend.db.repositories import MessageRepository

            await MessageRepository(ctx.db_path).create_message(db_id, "user", user_text.strip())
        except Exception:
            pass

        verdict = await ctx.orchestrator.handle_user_message(
            user_text,
            conversation_tail=hist,
            emitter_override=emitter,
            db_chat_session_id=db_id,
        )

        ctx.conversation.append(sid, "user", user_text.strip())
        assistant_spoken = str(verdict.message or "").strip()
        if assistant_spoken:
            ctx.conversation.append(sid, "assistant", assistant_spoken)
        emo = verdict.emotion or "neutral"

        try:
            from backend.db.repositories import MessageRepository

            repo = MessageRepository(ctx.db_path)
            if assistant_spoken:
                await repo.create_message(db_id, "assistant", assistant_spoken, emotion=str(emo))
        except Exception:
            pass

        await mgr.send_to_session(sid, "emotion", {"emotion": emo})

        await emit_chunks(str(verdict.message or ""), str(emo))

    await mgr.send_to_session(sid, "system_state", {"health": "ok", "session_id": sid})

    try:
        while True:
            envelope = await ws.receive_text()

            decoded: dict[str, Any]
            try:
                boxed = _json.loads(envelope)
                decoded = boxed if isinstance(boxed, dict) else {}
            except ValueError:


                decoded = {}

            parsed: _WsFrame | None


            try:
                parsed = _WsFrame.model_validate(decoded)
            except ValidationError:
                parsed = None


            evt = parsed.event.strip() if parsed else str(decoded.get("event") or "").strip()


            pdata = parsed.payload if parsed else decoded.get("payload")
            payload_map = pdata if isinstance(pdata, dict) else {}

            lowered = evt.casefold()

            if lowered == "ping":
                await ws.send_text(_json.dumps({"event": "pong", "payload": {}}, ensure_ascii=False))


                continue

            if lowered == "frontend_ready":

                await ensure_ws_db_session(ctx, sid)

                await mgr.send_to_session(
                    sid,
                    "system_state",
                    {"health": "ready", "session_id": sid},
                )


                continue

            if lowered == "chat_text":

                typed = str(payload_map.get("text") or "").strip()
                if typed:
                    ctx.orchestrator.phase = OrchestratorState.THINKING


                    await mgr.send_to_session(sid, "visual_state", {"state": "thinking"})

                    await process_text(typed)
                    ctx.orchestrator.phase = OrchestratorState.IDLE

                    await mgr.send_to_session(sid, "visual_state", {"state": "idle"})

                continue

            if lowered == "audio_duck":


                tv = payload_map.get("target_volume", 0.0)
                tvf = float(tv) if tv is not None else 0.0
                duck_data = {"target_volume": tvf, "ramp_ms": _int_ms(payload_map.get("ramp_ms", 160))}
                await mgr.send_to_session(sid, "audio_duck", duck_data)
                ctx.orchestrator.phase = OrchestratorState.LISTENING

                await mgr.send_to_session(sid, "visual_state", {"state": "listening"})


                continue

            if lowered == "ptt_start":

                ptt_payload = {"target_volume": 0.0, "ramp_ms": _int_ms(payload_map.get("ramp_ms", 160))}


                await mgr.send_to_session(sid, "audio_duck", ptt_payload)
                coord = getattr(ctx, "voice_input_coordinator", None)
                if coord is not None:
                    coord.set_frontend_ptt(True)
                ctx.orchestrator.phase = OrchestratorState.LISTENING
                await mgr.send_to_session(sid, "visual_state", {"state": "listening"})

                continue

            if lowered == "ptt_end":

                coord = getattr(ctx, "voice_input_coordinator", None)
                if coord is not None:
                    coord.set_frontend_ptt(False)

                ctx.orchestrator.phase = OrchestratorState.THINKING
                await mgr.send_to_session(sid, "visual_state", {"state": "thinking"})

                unwind = {"target_volume": 1.0, "ramp_ms": _int_ms(payload_map.get("ramp_ms", 160))}
                await mgr.send_to_session(sid, "audio_duck", unwind)

                transcription = ""

                decoder = getattr(ctx, "stt_engine", None)
                blob_b64 = str(payload_map.get("audio") or "").strip()
                if blob_b64 and decoder is not None:
                    pcm = base64.standard_b64decode(blob_b64)
                    try:


                        transcription = await decoder.transcribe(pcm)
                    except Exception:
                        transcription = ""

                clipped = transcription.strip()
                if clipped and getattr(ctx.config.audio, "strip_wake_phrase_from_transcription", True):
                    from backend.services.speech_transcription_clean import strip_wake_prefixes

                    prefixes = list(getattr(ctx.config.audio, "wake_transcription_prefixes", []) or [])
                    clipped = strip_wake_prefixes(clipped, prefixes)
                stt_payload: dict[str, Any] = {"text": clipped}
                if not blob_b64:
                    stt_payload["hint"] = "no_audio_payload"
                elif decoder is None:
                    stt_payload["hint"] = "stt_unconfigured"
                await mgr.send_to_session(sid, "stt_result", stt_payload)

                if clipped:
                    await process_text(clipped)

                ctx.orchestrator.phase = OrchestratorState.IDLE
                await mgr.send_to_session(sid, "visual_state", {"state": "idle"})

                continue

            dangling = str(payload_map.get("text") or "").strip()
            if dangling and not lowered:
                ctx.orchestrator.phase = OrchestratorState.THINKING


                await mgr.send_to_session(sid, "visual_state", {"state": "thinking"})
                await process_text(dangling)
                ctx.orchestrator.phase = OrchestratorState.IDLE

                await mgr.send_to_session(sid, "visual_state", {"state": "idle"})

    except WebSocketDisconnect:
        pass
    finally:
        mgr.disconnect(ws)
