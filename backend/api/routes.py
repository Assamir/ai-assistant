"""

REST dla Assystent (prefix /api/v1).

"""



from __future__ import annotations



import hmac

import json

import os

import uuid

from pathlib import Path
from typing import Annotated, Any, Literal, Optional

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
from backend.db.repositories import DailyCheckRepository, MessageRepository, ToolCallsRepository

router = APIRouter()




def _require_config_put_token(request: Request) -> None:

    expected = os.environ.get("ASSYSTENT_CONFIG_PUT_TOKEN", "").strip()

    if not expected:

        return

    header = request.headers.get("x-config-put-token", "").strip()

    auth = request.headers.get("authorization", "")

    bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""

    token = header or bearer

    if len(token) != len(expected) or not hmac.compare_digest(

        token.encode("utf-8"),

        expected.encode("utf-8"),

    ):

        raise HTTPException(

            status_code=401,

            detail=(

                "Brak lub nieprawidłowy token zapisu konfiguracji "

                "(nagłówek X-Config-Put-Token albo Authorization: Bearer)."

            ),

        )





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

async def api_config_put(request: Request, dep: Deps, body: ConfigPatchBody):

    _require_config_put_token(request)

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


class PlayerProfileGamePatchBody(BaseModel):
    league: Optional[str] = None
    game_version: Optional[str] = None


class PlayerProfileActiveCharacterBody(BaseModel):
    character: str = Field(..., min_length=1, max_length=256)


@router.patch("/player-profile/games/{game}")
async def api_player_profile_patch_game(game: str, body: PlayerProfileGamePatchBody, dep: Deps):
    store = dep.player_profile_store
    if store is None:
        raise HTTPException(status_code=503, detail={"code": "PLAYER_PROFILE_UNAVAILABLE"})
    fields_set = body.model_fields_set
    if "league" not in fields_set and "game_version" not in fields_set:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_PATCH"})
    out = store.patch_game_entry(
        game,
        league=body.league,
        game_version=body.game_version,
        update_league="league" in fields_set,
        update_game_version="game_version" in fields_set,
    )
    if out is None:
        raise HTTPException(status_code=404, detail={"code": "GAME_NOT_IN_PROFILE"})
    profile = out.pop("profile")
    if out.get("archive_recommended"):
        payload = {
            "game": out["game"],
            "previous_league": out.get("previous_league"),
            "league": out.get("league"),
            "archive_recommended": True,
            "hint": "POST /api/v1/player-profile/games/{game}/archive — profil YAML nie jest czyszczony automatycznie.",
        }
        for sid in dep.websocket_manager.iter_session_ids():
            try:
                await dep.websocket_manager.send_to_session(sid, "player_profile.league_changed", payload)
            except Exception:
                pass
    return {**out, "profile": json.loads(profile.model_dump_json())}


@router.post("/player-profile/games/{game}/active-character")
async def api_player_profile_set_active_character(game: str, body: PlayerProfileActiveCharacterBody, dep: Deps):
    store = dep.player_profile_store
    if store is None:
        raise HTTPException(status_code=503, detail={"code": "PLAYER_PROFILE_UNAVAILABLE"})
    result = store.set_active_character_name(game, body.character)
    if not result.get("ok"):
        code = str(result.get("error", "error"))
        if code == "game_not_in_profile":
            raise HTTPException(status_code=404, detail={"code": code})
        if code == "character_not_in_list":
            raise HTTPException(
                status_code=422,
                detail={"code": code, "characters": result.get("characters", [])},
            )
        raise HTTPException(status_code=400, detail={"code": code})
    profile = result.pop("profile")
    return {"active_character": result["active_character"], "profile": json.loads(profile.model_dump_json())}


class LeagueHintBody(BaseModel):
    broadcast: bool = False


@router.post("/player-profile/games/{game}/check-league-hint")
async def api_player_profile_check_league_hint(game: str, body: LeagueHintBody, dep: Deps):
    from backend.services.league_hint import analyze_league_hint, broadcast_player_profile_league_hint_ws

    out = await analyze_league_hint(dep, game)
    if not out.get("ok"):
        code = str(out.get("error", "error"))
        if code == "game_not_in_profile":
            raise HTTPException(status_code=404, detail={"code": code})
        if code == "no_player_profile":
            raise HTTPException(status_code=503, detail={"code": code})
        if code == "empty_game":
            raise HTTPException(status_code=400, detail={"code": code})
        if code == "web_search_unavailable":
            raise HTTPException(status_code=503, detail={"code": code, "hint": out.get("hint")})
        if code == "search_failed":
            raise HTTPException(status_code=502, detail={"code": code, "detail": out.get("detail")})
        raise HTTPException(status_code=500, detail={"code": code})
    if body.broadcast:
        await broadcast_player_profile_league_hint_ws(dep, out)
    return out






class PlayerProfileArchiveCreateBody(BaseModel):
    season: str = Field(..., min_length=1, max_length=512)
    reason: Literal["season_reset", "manual", "backup"]


@router.post("/player-profile/games/{game}/archive")
async def api_player_profile_archive_game(game: str, body: PlayerProfileArchiveCreateBody, dep: Deps):
    store = dep.player_profile_store
    if store is None:
        raise HTTPException(status_code=503, detail={"code": "PLAYER_PROFILE_UNAVAILABLE"})
    aid = await store.archive_game_entry(
        game_id=game,
        season=body.season,
        reason=body.reason,
    )
    if aid is None:
        raise HTTPException(status_code=404, detail={"code": "GAME_NOT_IN_PROFILE"})
    return {"archive_id": aid}


@router.get("/player-profile/archives")
async def api_player_profile_archives(dep: Deps, game: str | None = None, limit: int = 50):
    store = dep.player_profile_store
    if store is None:
        return {"archives": []}
    rows = await store.list_archives(game=game, limit=limit)
    out = []
    for r in rows:
        item = {
            "id": r["id"],
            "game": r["game"],
            "season": r["season"],
            "reason": r["reason"],
            "archive_date": r["archive_date"],
        }
        snap = r.get("yaml_snapshot")
        if snap is not None:
            item["yaml_snapshot"] = snap
        out.append(item)
    return {"archives": out}


class ImportBuildBody(BaseModel):
    url: str = Field(..., min_length=10, max_length=2048)


@router.post("/player-profile/games/{game}/import-build")
async def api_import_build(game: str, body: ImportBuildBody, dep: Deps):
    """Scrape *url*, extract build data with LLM, upsert into player profile."""
    from backend.services.build_import import import_build_from_url

    store = dep.player_profile_store
    if store is None:
        raise HTTPException(status_code=503, detail={"code": "PLAYER_PROFILE_UNAVAILABLE"})
    if dep.tool_registry is None:
        raise HTTPException(status_code=503, detail={"code": "MCP_UNAVAILABLE"})
    result = await import_build_from_url(dep, game, body.url)
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail={"code": "IMPORT_FAILED", "error": result.get("error")})
    mgr = dep.websocket_manager
    if mgr is not None:
        for sid in mgr.iter_session_ids():
            await mgr.send_to_session(sid, "player_profile.build_imported", {
                "game": game,
                "character": result.get("character"),
                "build": result.get("build"),
                "url": body.url,
            })
    return result


class DailyCheckRunBody(BaseModel):
    game: str = Field(..., min_length=1, max_length=64)
    force: bool = False


@router.post("/daily-checks/run")
async def api_daily_checks_run(body: DailyCheckRunBody, dep: Deps):
    from backend.services.daily_meta_check import run_daily_meta_check_for_game

    out = await run_daily_meta_check_for_game(dep, body.game, force=body.force, broadcast=True)
    if not out.get("ok"):
        code = str(out.get("error", "error"))
        if code == "game_not_in_profile":
            raise HTTPException(status_code=404, detail={"code": code})
        if code == "no_player_profile":
            raise HTTPException(status_code=503, detail={"code": code})
        raise HTTPException(status_code=400, detail={"code": code})
    return out


@router.get("/daily-checks")
async def api_daily_checks_list(dep: Deps, game: str | None = None, limit: int = 50):
    repo = DailyCheckRepository(dep.db_path)
    rows = await repo.list_recent(game=game, limit=limit)
    for r in rows:
        r["has_changes"] = bool(r.get("has_changes"))
        r["user_notified"] = bool(r.get("user_notified"))
    return {"checks": rows}


@router.post("/backup")
async def api_backup_run(dep: Deps):
    """Tworzy kopię zapasową content_root jako ZIP."""
    from pathlib import Path
    from backend.services.backup_service import run_backup

    root = Path(dep.config.general.content_root).expanduser()

    async def _bcast(ev: str, pl: dict) -> None:
        for sid in dep.websocket_manager.iter_session_ids():
            await dep.websocket_manager.send_to_session(sid, ev, pl)

    result = await run_backup(root, broadcast_fn=_bcast)
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail={"code": "BACKUP_FAILED", "error": result.get("error")})
    return result


@router.delete("/knowledge")
async def api_knowledge_delete(dep: Deps, source_path: str):
    """Usuwa chunki bazy wiedzy według ``source_path`` (np. ``stellaris.md``). Wymaga memory.enabled=true."""
    sr = dep.semantic_recall
    if sr is None:
        raise HTTPException(status_code=503, detail={"code": "MEMORY_UNAVAILABLE", "hint": "memory.enabled: false w konfiguracji"})
    removed = sr.remove_knowledge_chunks_where({"source_path": source_path})
    return {"ok": True, "removed": removed, "source_path": source_path}


@router.get("/personas")
async def api_personas(dep: Deps):
    """Lista plików person dostępnych w personas/ oraz aktywna persona."""
    pl = dep.persona_loader
    personas = []
    try:
        for p in sorted(pl._dir.glob("*.md")):
            try:
                loaded = pl.load(p.stem)
                personas.append({"id": p.stem, "display_name": loaded.frontmatter.display_name})
            except Exception:
                personas.append({"id": p.stem, "display_name": p.stem})
    except Exception:
        pass
    active = dep.orchestrator.state.get("active_persona") or "aria"
    return {"personas": personas, "active": active}


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


