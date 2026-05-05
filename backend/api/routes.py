"""

REST dla Assystent (prefix /api/v1).

"""



from __future__ import annotations



import json

import uuid

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form

from fastapi.responses import JSONResponse, Response, StreamingResponse

from pydantic import BaseModel, Field, ValidationError

import yaml

from backend.api.app_context import AppContext, ensure_ws_db_session
from backend.config.loader import ConfigLoader
from backend.config.schema import ConfigSchema
from backend.services.health import build_health_snapshot
from backend.services.config_hot_reload import _broadcast_reload
from backend.services.runtime_config import apply_reload_configuration
from backend.db.repositories import MessageRepository, ToolCallsRepository

router = APIRouter()





def ctx_dep(request: Request) -> AppContext:



    ctx = getattr(request.app.state, "ctx", None)

    if ctx is None:

        raise RuntimeError("App context not initialized — check lifespan startup.")



    return ctx





Deps = Annotated[AppContext, Depends(ctx_dep)]





@router.get("/status")

async def api_status(dep: Deps):

    snap = build_health_snapshot(dep)

    return JSONResponse(

        {

            "app": {"name": "assystent-backend", "version": "0.4.0-dev"},

            "health": snap,

            "llm": {

                "api_base_url": dep.config.llm.api_base_url,

                "circuit_breaker": snap["components"]["llm"]["circuit_breaker"],

            },

            "orchestrator": {"phase": dep.orchestrator.phase.value},

            "persona": {"active": dep.orchestrator.state.get("active_persona", "default")},

            "observer": {

                "running": dep.game_observer.is_running if dep.game_observer else False,

                "vision_loop_running": dep.observer_loop.is_running if dep.observer_loop else False,

                "current_game": dep.orchestrator.state.get("current_game"),

            },
            "memory": {
                "enabled": dep.config.memory.enabled,
                "recall_active": dep.semantic_recall is not None,
                "watching": dep.knowledge_watcher is not None,
            },
        }

    )





@router.get("/health")

async def api_health(dep: Deps):



    snap = build_health_snapshot(dep)

    return {
        "status": snap["overall"],
        "llm_breaker": snap["components"]["llm"]["circuit_breaker"],
        "components": snap["components"],
    }





@router.get("/config")

async def api_config(dep: Deps):

    return {"data": json.loads(dep.config.model_dump_json())}




class ConfigPatchBody(BaseModel):

    """Częściowa aktualizacja — zagnieżdżone klucze mergują się jak przy YAML (ConfigLoader)."""

    patch: dict[str, Any] = Field(default_factory=dict)


@router.put("/config")

async def api_config_put(dep: Deps, body: ConfigPatchBody):

    if not dep.resolved_config_path:

        raise HTTPException(

            status_code=409,

            detail=(

                "Brak pliku konfiguracji na dysku — utwórz config/config.yaml "

                "w content_root lub ustaw ASSY_GENERAL__CONTENT_ROOT."

            ),

        )

    path = Path(dep.resolved_config_path)

    loader = ConfigLoader()

    merged = loader._merge_dicts(dep.config.model_dump(), body.patch)

    try:

        new_cfg = ConfigSchema.model_validate(merged)

    except ValidationError as exc:

        raise HTTPException(status_code=422, detail={"errors": exc.errors()}) from exc

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as fh:

        yaml.safe_dump(

            new_cfg.model_dump(mode="json"),

            fh,

            allow_unicode=True,

            sort_keys=False,

            default_flow_style=False,

        )

    await apply_reload_configuration(dep, new_cfg)

    await _broadcast_reload(dep, "config")

    return {"ok": True, "data": json.loads(new_cfg.model_dump_json())}




@router.get("/player-profile")

async def api_player_profile(dep: Deps):

    store = dep.player_profile_store

    if store is None:

        return {"path": None, "profile": None}

    prof = store.load()

    return {"path": str(store.path), "profile": json.loads(prof.model_dump_json())}







@router.get('/tools')
async def api_tools(dep: Deps):
    """Lista zarejestrowanych narzedzi MCP dostepnych dla LLM."""
    return {
        'tools': [
            {
                'name': t['function']['name'],
                'description': t['function'].get('description', ''),
            }
            for t in dep.tool_registry.openai_tools()
        ]
    }

class VoiceSynthBody(BaseModel):

    text: str = Field(..., min_length=1, max_length=4000)

    emotion: str = "neutral"





@router.post("/voice/synthesize")

async def voice_synthesize(body: VoiceSynthBody, dep: Deps):



    tts = getattr(dep, "tts_engine", None)

    if tts is None:

        raise HTTPException(status_code=503, detail={"code": "TTS_UNAVAILABLE"})

    wav = await tts.speak(body.text, emotion=body.emotion)

    return Response(content=wav, media_type="audio/wav")





@router.post("/voice/transcribe")

async def voice_transcribe(

    dep: Deps,



    audio: Annotated[UploadFile, File(...)],

):



    stt = getattr(dep, "stt_engine", None)

    if stt is None:

        raise HTTPException(status_code=503, detail={"code": "STT_UNAVAILABLE"})

    raw = await audio.read()

    try:

        text = await stt.transcribe(raw)

        confidence = await stt.get_confidence(raw)

    except Exception as exc:

        raise HTTPException(status_code=422, detail=str(exc)) from exc



    floor = getattr(dep.config.stt, "confidence_floor", 0.45)



    if confidence >= 0.7:

        hint = "process"

    elif confidence >= floor:

        hint = "confirm"

    else:

        hint = "reject"



    return {

        "text": text,



        "language": dep.config.stt.language,



        "confidence": confidence,



        "action_hint": hint,

    }





class VoiceChatBody(BaseModel):

    text: str = Field(..., min_length=1, max_length=8000)

    stream: bool = False

    session_id: str | None = None





@router.post("/voice/chat")

async def voice_chat(body: VoiceChatBody, dep: Deps, request: Request):



    sess = body.session_id or str(uuid.uuid4())

    hist = dep.conversation.tail(sess)



    accept = request.headers.get("accept", "")

    wants_sse = body.stream or ("text/event-stream" in accept.lower())





    if wants_sse:

        orch = dep.orchestrator

        async def gen():

            from backend.core.emotion_parser import parse_emotion_tag

            db_id = await ensure_ws_db_session(dep, sess)
            msg_repo = MessageRepository(dep.db_path)
            await msg_repo.create_message(db_id, "user", body.text.strip())

            pieces: list[str] = []
            async for chunk in orch.stream_reply_tokens(body.text, history_tail=hist):
                pieces.append(chunk)
                yield f"event: token\ndata: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"

            assembled = "".join(pieces)

            emotion, stripped_body = parse_emotion_tag(assembled)
            yield f"event: emotion\ndata: {json.dumps({'emotion': emotion}, ensure_ascii=False)}\n\n"

            dep.conversation.append(sess, "user", body.text)
            reply_plain = stripped_body.strip()
            if reply_plain:
                dep.conversation.append(sess, "assistant", reply_plain)
                try:
                    await msg_repo.create_message(
                        db_id,
                        "assistant",
                        reply_plain,
                        emotion=str(emotion or "neutral"),
                    )
                except Exception:
                    pass

            # Ścieżka stream bez narzędzi — spójność API z JSON (puste tool_calls).
            yield f"event: done\ndata: {json.dumps({'ok': True, 'session_id': sess, 'chat_session_id': db_id, 'tool_calls': []}, ensure_ascii=False)}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")



    db_id = await ensure_ws_db_session(dep, sess)
    msg_repo = MessageRepository(dep.db_path)
    user_mid = await msg_repo.create_message(db_id, "user", body.text.strip())

    outcome = await dep.orchestrator.handle_user_message(
        body.text,
        conversation_tail=hist,
        system_health="healthy",
        db_chat_session_id=db_id,
    )

    dep.conversation.append(sess, "user", body.text)

    emo = str(outcome.emotion or "neutral")
    if outcome.message:

        dep.conversation.append(sess, "assistant", str(outcome.message))
        try:
            await msg_repo.create_message(
                db_id,
                "assistant",
                str(outcome.message).strip(),
                emotion=emo,
            )
        except Exception:
            pass

    tool_rows = await ToolCallsRepository(dep.db_path).list_for_chat_after_message(db_id, user_mid)
    tool_calls_payload = [
        {
            "id": int(r["id"]),
            "message_id": int(r["message_id"]),
            "tool_name": r["tool_name"],
            "success": bool(r["success"]),
            "duration_ms": int(r["duration_ms"] or 0),
        }
        for r in tool_rows
    ]

    mid = uuid.uuid4().int % (10**9)

    return {
        "message_id": mid,
        "content": outcome.message or "",
        "emotion": outcome.emotion,
        "tool_calls": tool_calls_payload,
        "duration_ms": 0,
        "language_used": "pl",
        "session_id": sess,
        "chat_session_id": db_id,
    }





class VoiceProcessMeta(BaseModel):

    session_id: str | None = None





@router.post("/voice/process")



async def voice_process(

    dep: Deps,

    audio: Annotated[UploadFile, File(...)],

    metadata: str | None = Form(None),

):



    stt = getattr(dep, "stt_engine", None)

    if stt is None:

        raise HTTPException(status_code=503, detail={"code": "STT_UNAVAILABLE"})

    raw = await audio.read()

    user_text = await stt.transcribe(raw)



    sess_extra: str | None = None

    if metadata:

        try:



            mobj = VoiceProcessMeta.model_validate_json(metadata)



            sess_extra = mobj.session_id



        except Exception:



            sess_extra = None



    sess = sess_extra or str(uuid.uuid4())

    hist = dep.conversation.tail(sess)

    db_id = await ensure_ws_db_session(dep, sess)
    msg_repo = MessageRepository(dep.db_path)
    await msg_repo.create_message(db_id, "user", user_text.strip())

    outcome = await dep.orchestrator.handle_user_message(
        user_text,
        conversation_tail=hist,
        system_health="healthy",
        db_chat_session_id=db_id,
    )

    dep.conversation.append(sess, "user", user_text)





    if outcome.message:
        dep.conversation.append(sess, "assistant", str(outcome.message))
        try:
            await msg_repo.create_message(
                db_id,
                "assistant",
                str(outcome.message).strip(),
                emotion=str(outcome.emotion or "neutral"),
            )
        except Exception:
            pass

    tts = getattr(dep, "tts_engine", None)





    if tts is None:

        raise HTTPException(status_code=503, detail={"code": "TTS_UNAVAILABLE"})

    wav = await tts.speak(outcome.message or "", emotion=outcome.emotion)

    hdrs = {"X-Emotion": str(outcome.emotion or "neutral"), "X-Duration-Ms": "0"}





    return Response(content=wav, media_type="audio/wav", headers=hdrs)


