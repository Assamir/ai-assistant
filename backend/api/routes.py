"""

REST dla Assystent (prefix /api/v1).

"""



from __future__ import annotations



import json

import uuid

from typing import Annotated



from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form

from fastapi.responses import JSONResponse, Response, StreamingResponse

from pydantic import BaseModel, Field



from backend.api.app_context import AppContext
from backend.services.health import build_health_snapshot



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

                "current_game": dep.orchestrator.state.get("current_game"),

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

            yield f"event: done\ndata: {json.dumps({'ok': True}, ensure_ascii=False)}\n\n"



        return StreamingResponse(gen(), media_type="text/event-stream")



    outcome = await dep.orchestrator.handle_user_message(

        body.text,

        conversation_tail=hist,

        system_health="healthy",

    )

    dep.conversation.append(sess, "user", body.text)

    if outcome.message:



        dep.conversation.append(sess, "assistant", str(outcome.message))

    mid = uuid.uuid4().int % (10**9)



    return {

        "message_id": mid,



        "content": outcome.message or "",

        "emotion": outcome.emotion,

        "tool_calls": [],



        "duration_ms": 0,

        "language_used": "pl",

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





    outcome = await dep.orchestrator.handle_user_message(

        user_text,

        conversation_tail=hist,



        system_health="healthy",

    )

    dep.conversation.append(sess, "user", user_text)





    if outcome.message:

        dep.conversation.append(sess, "assistant", str(outcome.message))





    tts = getattr(dep, "tts_engine", None)





    if tts is None:

        raise HTTPException(status_code=503, detail={"code": "TTS_UNAVAILABLE"})

    wav = await tts.speak(outcome.message or "", emotion=outcome.emotion)

    hdrs = {"X-Emotion": str(outcome.emotion or "neutral"), "X-Duration-Ms": "0"}





    return Response(content=wav, media_type="audio/wav", headers=hdrs)


