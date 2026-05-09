"""Współdzielony stan HTTP/WS dla FastAPI."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from backend.ai.llm_client import LMStudioClient
from backend.ai.voice_input import WakewordDetector
from backend.config.loader import ConfigLoader
from backend.config.paths import resolve_config_yaml, sqlite_database_path
from backend.config.schema import ConfigSchema
from backend.core.command_matching import CommandMatcher
from backend.core.interfaces import BaseSTTEngine, BaseTTSEngine, BaseVLMAnalyzer, BaseOCREngine, BaseScreenCapture
from backend.core.orchestrator import ConversationOrchestrator
from backend.core.persona_loader import PersonaLoader
from backend.core.prompt_builder import PromptBuilder
from backend.db.migration_runner import MigrationRunner
from backend.memory.knowledge_ingester import KnowledgeDirectoryWatcher, KnowledgeIngester
from backend.memory.semantic_recall import SemanticRecall
from backend.mcp.registry import ToolRegistry, build_default_tool_registry
from backend.services.game_observer import GameObserver
from backend.services.game_profile import build_game_profile_index
from backend.services.observer_pause import ObserverPauseManager
from backend.services.player_profile import PlayerProfileRepository
from backend.services.session_watchdog import recover_stale_sessions

_logger = logging.getLogger(__name__)


@dataclass
class ConversationStore:
    """Kolejka ostatnich wiadomości user/assistant (per sesja WS)."""

    max_messages: int = 40
    _msgs: Dict[str, List[Dict[str, str]]] = field(default_factory=dict)

    def tail(self, session_id: str) -> List[Dict[str, str]]:
        return list(self._msgs.get(session_id, [])[-self.max_messages :])

    def append(self, session_id: str, role: str, content: str) -> None:
        q = self._msgs.setdefault(session_id, [])
        q.append({"role": role, "content": content})
        overflow = len(q) - self.max_messages
        if overflow > 0:
            del q[0:overflow]


class WebSocketManager:
    """Multiplexed events: `{event: str, payload: object}`."""

    __slots__ = ("_by_session", "_ws_to_sid")

    def __init__(self) -> None:
        self._by_session: Dict[str, List[Any]] = {}
        self._ws_to_sid: Dict[int, str] = {}

    def bind(self, websocket: Any, session_id: Optional[str] = None) -> str:
        sid = session_id or str(uuid.uuid4())
        self._ws_to_sid[id(websocket)] = sid
        self._by_session.setdefault(sid, []).append(websocket)
        return sid

    def disconnect(self, websocket: Any) -> None:
        wid = id(websocket)
        sid = self._ws_to_sid.pop(wid, None)
        if not sid:
            return
        conns = [w for w in self._by_session.get(sid, []) if id(w) != wid]
        if conns:
            self._by_session[sid] = conns
        else:
            self._by_session.pop(sid, None)

    async def send_to_session(self, session_id: str, event: str, payload: dict) -> None:
        import json as _json

        frame = _json.dumps({"event": event, "payload": payload}, ensure_ascii=False)
        for ws in list(self._by_session.get(session_id, [])):
            try:
                await ws.send_text(frame)
            except Exception:
                self.disconnect(ws)

    def iter_session_ids(self) -> List[str]:
        return list(self._by_session.keys())


@dataclass
class AppContext:

    config: ConfigSchema
    resolved_config_path: Optional[str]
    db_path: str
    conversation: ConversationStore
    prompt_builder: PromptBuilder
    persona_loader: PersonaLoader

    tool_registry: ToolRegistry

    command_matcher: CommandMatcher
    llm_client: LMStudioClient
    orchestrator: ConversationOrchestrator
    websocket_manager: WebSocketManager
    stt_engine: Optional[BaseSTTEngine] = None
    tts_engine: Optional[BaseTTSEngine] = None
    game_observer: Optional[GameObserver] = None
    voice_input_coordinator: Optional[Any] = None  # VoiceInputCoordinator — ustawiane w lifespan
    wakeword_detector: Optional[WakewordDetector] = None
    vlm_engine: Optional[BaseVLMAnalyzer] = None
    ocr_engine: Optional[BaseOCREngine] = None
    vision_pipeline: Optional[Any] = None  # DualVisionPipeline — budowany przy starcie
    screen_capture: Optional[BaseScreenCapture] = None
    observer_loop: Optional[Any] = None  # ObserverLoop — po create_app_context
    db_session_by_ws: Dict[str, int] = field(default_factory=dict)
    game_profiles: Dict[str, Any] = field(default_factory=dict)
    observer_pause_manager: Optional[Any] = None
    semantic_recall: Optional[SemanticRecall] = None
    knowledge_ingester: Optional[KnowledgeIngester] = None
    knowledge_watcher: Optional[KnowledgeDirectoryWatcher] = None
    player_profile_store: Optional[PlayerProfileRepository] = None


def init_semantic_memory(
    cfg: ConfigSchema,
    root: Path,
) -> tuple[Optional[SemanticRecall], Optional[KnowledgeIngester], Optional[KnowledgeDirectoryWatcher]]:
    """Tworzy SemanticRecall + opcjonalny ingest / watcher wg ``cfg.memory``."""
    if not cfg.memory.enabled:
        return None, None, None

    persist_path: Optional[str] = None
    if cfg.memory.chroma_persist:
        chroma_dir = (root / "data" / cfg.memory.chroma_subdir).resolve()
        chroma_dir.mkdir(parents=True, exist_ok=True)
        persist_path = str(chroma_dir)
    sr = SemanticRecall(persist_directory=persist_path)
    ing = KnowledgeIngester(
        sr,
        chunk_size=cfg.memory.chunk_size,
        chunk_overlap=cfg.memory.chunk_overlap,
        max_total_chunks=cfg.memory.max_kb_chunks,
    )
    kb_dir = (root / cfg.memory.knowledge_dir).resolve()
    kb_dir.mkdir(parents=True, exist_ok=True)
    watcher: Optional[KnowledgeDirectoryWatcher] = None
    if cfg.memory.ingest_on_startup:
        try:
            n = ing.ingest_directory(kb_dir)
            _logger.info("Knowledge ingest (%s): %s chunks", kb_dir, n)
        except Exception as exc:
            _logger.warning("Knowledge ingest failed: %s", exc)
    if cfg.memory.watch_knowledge:
        watcher = KnowledgeDirectoryWatcher(ing, kb_dir)
        try:
            watcher.start()
        except Exception as exc:
            _logger.warning("Knowledge watcher not started: %s", exc)
            watcher = None
    return sr, ing, watcher


async def ensure_ws_db_session(ctx: AppContext, ws_sid: str) -> int:
    """Tworzy wiersz `sessions` dla klucza sesji klienta (WebSocket `sid` albo `session_id` z REST voice).

    Mapa `db_session_by_ws` jest współdzielona: ten sam identyfikator (np. UUID z body) daje ten sam `sessions.id`
    przy kolejnych żądaniach HTTP lub po rekonnekcie WS.
    """
    existing = ctx.db_session_by_ws.get(ws_sid)
    if existing is not None:
        return existing
    from backend.db.repositories import SessionRepository

    repo = SessionRepository(ctx.db_path)
    game = ctx.orchestrator.state.get("current_game")
    g = game if isinstance(game, str) else None
    db_id = await repo.start_session(game_detected=g)
    ctx.db_session_by_ws[ws_sid] = db_id
    try:
        await record_player_profile_snapshot_session_start(ctx, db_id)
    except Exception:
        pass
    return db_id


async def record_player_profile_snapshot_session_start(ctx: AppContext, db_id: int) -> None:
    """``player_context_snapshots`` przy pierwszym utworzeniu sesji czatu (jeśli jest profil)."""
    store = ctx.player_profile_store
    if store is None:
        return
    game = ctx.orchestrator.state.get("current_game")
    if not isinstance(game, str) or not game.strip():
        return
    await store.record_snapshot(session_id=db_id, game_id=game.strip(), trigger="session_start")


def try_build_stt_engine(cfg: ConfigSchema) -> Optional[BaseSTTEngine]:
    """Tworzy FasterWhisperSTT z configu; zwraca None przy braku pakietu."""
    try:
        from backend.ai.faster_whisper_stt import FasterWhisperSTT
        return FasterWhisperSTT(cfg.stt)
    except ImportError:
        _logger.info("faster-whisper not installed — STT engine disabled")
    except Exception as exc:
        _logger.warning("STT engine init failed: %s", exc)
    return None


def try_build_tts_engine(cfg: ConfigSchema) -> Optional[BaseTTSEngine]:
    """Tworzy PiperTTS jeśli piper_voice_onnx_path jest ustawiony; inaczej None."""
    if not cfg.tts.piper_voice_onnx_path:
        return None
    try:
        from backend.ai.piper_tts import PiperTTS
        return PiperTTS(cfg.tts)
    except ImportError:
        _logger.info("piper dependencies not installed — TTS engine disabled")
    except Exception as exc:
        _logger.warning("TTS engine init failed: %s", exc)
    return None


def try_build_vlm_engine(cfg: ConfigSchema) -> Optional[BaseVLMAnalyzer]:
    """Moondream2 gdy `vlm.enabled`; wagi ładują się przy pierwszej inferencji."""
    if not cfg.vlm.enabled:
        return None
    try:
        from backend.ai.moondream_vlm import Moondream2VLM

        return Moondream2VLM(cfg.vlm)
    except ImportError:
        _logger.info("Moondream VLM unavailable")
    except Exception as exc:
        _logger.warning("VLM engine init failed: %s", exc)
    return None


def try_build_ocr_engine(cfg: ConfigSchema) -> Optional[BaseOCREngine]:
    """EasyOCR przy `ocr.enabled`; pierwszy odczyt ładuje Reader."""
    if not cfg.ocr.enabled:
        return None
    try:
        import easyocr  # noqa: F401
    except ImportError:
        _logger.info("Pakiet easyocr nie jest zainstalowany — OCR wyłączony (pip install easyocr).")
        return None
    try:
        from backend.ai.easyocr_engine import EasyOCREngine
    except ImportError:
        _logger.info("Moduł EasyOCREngine niedostępny — OCR wyłączony")
        return None

    try:
        return EasyOCREngine(cfg.ocr)
    except Exception as exc:
        _logger.warning("OCR engine init failed: %s", exc)
        if cfg.ocr.use_gpu:
            try:
                ocr_cpu = cfg.ocr.model_copy(update={"use_gpu": False})
                eng = EasyOCREngine(ocr_cpu)
                _logger.info("EasyOCR: ponowiono inicjalizację w trybie CPU (po błędzie GPU).")
                return eng
            except Exception as exc2:  # pragma: no cover - zależne od CUDA
                _logger.warning("OCR CPU fallback failed: %s", exc2)
        return None


def build_vision_pipeline(
    cfg: ConfigSchema,
    vlm: Optional[BaseVLMAnalyzer],
    ocr: Optional[BaseOCREngine],
) -> Optional[Any]:
    """Potok VLM+OCR; None gdy brak obu silników."""
    if vlm is None and ocr is None:
        return None
    from backend.ai.vision_pipeline import DualVisionPipeline

    return DualVisionPipeline(vlm_engine=vlm, ocr_engine=ocr, ocr_config=cfg.ocr)


def load_resolved_config() -> tuple[ConfigSchema, Optional[str], Path]:
    """Defaults + env, potem YAML z content_root jeśli istnieje."""
    loader = ConfigLoader()
    preliminary = loader.load_config(None)
    root = Path(preliminary.general.content_root).expanduser()
    yaml_path = resolve_config_yaml(root)
    if yaml_path is not None:
        cfg = loader.load_config(str(yaml_path))
        return cfg, str(yaml_path), root
    return preliminary, None, root


def create_app_context() -> AppContext:
    cfg, yaml_path, root = load_resolved_config()
    data_parent = root / "data"
    data_parent.mkdir(parents=True, exist_ok=True)
    db_path = str(sqlite_database_path(root))
    MigrationRunner(db_path).run_migrations()
    recover_stale_sessions(db_path)

    personas_dir = root / "personas"
    personas_dir.mkdir(parents=True, exist_ok=True)

    semantic_recall, knowledge_ingester, knowledge_watcher = init_semantic_memory(cfg, root)

    player_profile_store = PlayerProfileRepository(
        str((root / "data" / "player_profile.yaml").resolve()),
        db_path,
    )

    reg = build_default_tool_registry(
        db_path=db_path,
        mcp_cfg=cfg.mcp,
        content_root=str(root.resolve()),
    )
    matcher = CommandMatcher(fuzzy=cfg.ai_runtime.command_match_fuzzy)
    llm = LMStudioClient(cfg.llm)
    pb = PromptBuilder(max_context_tokens=cfg.ai_runtime.max_context_tokens)
    pl = PersonaLoader(personas_dir)

    orch = ConversationOrchestrator(
        configuration=cfg,
        lm_client=llm,
        prompt_builder=pb,
        persona_loader=pl,
        command_matcher=matcher,
        tool_registry=reg,
        active_persona="default",
        emitter=None,
        db_path=db_path,
        semantic_recall=semantic_recall,
        player_profile_repo=player_profile_store,
    )

    profiles = build_game_profile_index(root, cfg)

    obs = GameObserver(
        cfg.observer,
        orchestrator_state=orch.state,
        profiles_by_id=profiles,
    )
    wake = WakewordDetector(
        enabled=cfg.audio.wakeword_enabled,
        wakeword_models=list(cfg.audio.wakeword_models),
        threshold=cfg.audio.wakeword_threshold,
    )

    vlm = try_build_vlm_engine(cfg)
    ocr = try_build_ocr_engine(cfg)
    vp = build_vision_pipeline(cfg, vlm, ocr)

    from backend.ai.screen_capture import DesktopScreenCapture
    from backend.services.observer_loop import ObserverLoop

    screen = DesktopScreenCapture()

    ctx = AppContext(
        config=cfg,
        resolved_config_path=yaml_path,
        db_path=db_path,
        conversation=ConversationStore(),
        prompt_builder=pb,
        persona_loader=pl,
        tool_registry=reg,
        command_matcher=matcher,
        llm_client=llm,
        orchestrator=orch,
        websocket_manager=WebSocketManager(),
        stt_engine=try_build_stt_engine(cfg),
        tts_engine=try_build_tts_engine(cfg),
        game_observer=obs,
        wakeword_detector=wake,
        vlm_engine=vlm,
        ocr_engine=ocr,
        vision_pipeline=vp,
        screen_capture=screen,
        observer_loop=None,
        game_profiles=profiles,
        semantic_recall=semantic_recall,
        knowledge_ingester=knowledge_ingester,
        knowledge_watcher=knowledge_watcher,
        player_profile_store=player_profile_store,
    )
    ctx.observer_loop = ObserverLoop(ctx)
    ctx.observer_pause_manager = ObserverPauseManager(ctx)

    async def _vlm_fallback() -> Any:
        from backend.services.game_vlm_fallback import probe_game_identity_from_screen

        return await probe_game_identity_from_screen(ctx)

    if ctx.game_observer is not None:
        ctx.game_observer.set_vlm_fallback(_vlm_fallback)

    from backend.mcp.context_tools import register_context_dependent_mcp_tools

    register_context_dependent_mcp_tools(ctx)

    # Wiring voice→REST callables (unikamy circular dep: ctx → orch → ctx)
    from backend.services.league_hint import analyze_league_hint
    from backend.services.daily_meta_check import run_daily_meta_check_for_game
    from backend.services.build_import import import_build_from_url

    async def _league_hint_fn(game_id: str) -> dict:
        return await analyze_league_hint(ctx, game_id)

    async def _daily_check_fn(game_id: str, force: bool = False) -> dict:
        return await run_daily_meta_check_for_game(ctx, game_id, force=force, broadcast=True)

    async def _import_build_fn(game_id: str, url: str) -> dict:
        return await import_build_from_url(ctx, game_id, url)

    orch._league_hint_fn = _league_hint_fn
    orch._daily_check_fn = _daily_check_fn
    orch._import_build_fn = _import_build_fn

    return ctx


def make_game_emitter(ctx: AppContext):
    """Returns an async emitter that updates orchestrator state and broadcasts over WebSocket."""
    async def _emit(event_name: str, payload: Mapping[str, Any]) -> None:
        if event_name == "game_detected":
            ctx.orchestrator.state["current_game"] = payload.get("game")
            gid = payload.get("game_id")
            if gid:
                ctx.orchestrator.state["current_game_profile_id"] = gid
            elif not payload.get("active"):
                ctx.orchestrator.state.pop("current_game_profile_id", None)
            from backend.services.game_detection_tracking import record_game_detection_on_game_emit

            await record_game_detection_on_game_emit(ctx, payload)
        for sid in list(ctx.websocket_manager._by_session.keys()):
            await ctx.websocket_manager.send_to_session(sid, event_name, dict(payload))
        if event_name == "game_detected":
            await _maybe_auto_league_hint_after_game_detected(ctx, payload)
            await _maybe_auto_session_report_after_game_stopped(ctx, payload)
    return _emit


async def _maybe_auto_session_report_after_game_stopped(ctx: AppContext, payload: Mapping[str, Any]) -> None:
    """Gdy gra się kończy i `observer.auto_session_report` jest włączone — emituje `auto_session_report_start` do aktywnych sesji WS."""
    if payload.get("active"):
        return
    if not ctx.config.observer.auto_session_report:
        return
    session_ids = list(ctx.websocket_manager._by_session.keys())
    if not session_ids:
        return
    for sid in session_ids:
        try:
            await ctx.websocket_manager.send_to_session(sid, "auto_session_report_start", {})
        except Exception:
            _logger.debug("auto_session_report_start send failed for session %s", sid)


async def _maybe_auto_league_hint_after_game_detected(ctx: AppContext, payload: Mapping[str, Any]) -> None:
    """Opcjonalny `check-league-hint` po wykryciu gry — `observer.auto_league_hint_on_game_detected` lub `ASSY_OBSERVER__AUTO_LEAGUE_HINT_ON_GAME_DETECTED`."""
    if not payload.get("active"):
        return
    raw_gid = payload.get("game_id")
    if not isinstance(raw_gid, str) or not raw_gid.strip():
        return
    if not ctx.config.observer.auto_league_hint_on_game_detected:
        return
    from backend.services.league_hint import analyze_league_hint, broadcast_player_profile_league_hint_ws

    try:
        out = await analyze_league_hint(ctx, raw_gid.strip())
    except Exception:
        _logger.debug("Auto league hint after game_detected failed", exc_info=True)
        return
    await broadcast_player_profile_league_hint_ws(ctx, out)


__all__ = [
    "AppContext",
    "ConversationStore",
    "WebSocketManager",
    "create_app_context",
    "make_game_emitter",
    "load_resolved_config",
    "try_build_stt_engine",
    "try_build_tts_engine",
    "try_build_vlm_engine",
    "try_build_ocr_engine",
    "build_vision_pipeline",
    "ensure_ws_db_session",
    "init_semantic_memory",
]
