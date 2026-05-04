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
from backend.core.interfaces import BaseSTTEngine, BaseTTSEngine, BaseVLMAnalyzer
from backend.core.orchestrator import ConversationOrchestrator
from backend.core.persona_loader import PersonaLoader
from backend.core.prompt_builder import PromptBuilder
from backend.db.migration_runner import MigrationRunner
from backend.mcp.registry import ToolRegistry, build_default_tool_registry
from backend.services.game_observer import GameObserver
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

    reg = build_default_tool_registry()
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
    )

    obs = GameObserver(cfg.observer)
    wake = WakewordDetector(
        enabled=cfg.audio.wakeword_enabled,
        wakeword_models=list(cfg.audio.wakeword_models),
        threshold=cfg.audio.wakeword_threshold,
    )

    return AppContext(
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
        vlm_engine=try_build_vlm_engine(cfg),
    )


def make_game_emitter(ctx: AppContext):
    """Returns an async emitter that updates orchestrator state and broadcasts over WebSocket."""
    async def _emit(event_name: str, payload: Mapping[str, Any]) -> None:
        if event_name == "game_detected":
            ctx.orchestrator.state["current_game"] = payload.get("game")
        for sid in list(ctx.websocket_manager._by_session.keys()):
            await ctx.websocket_manager.send_to_session(sid, event_name, dict(payload))
    return _emit


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
]
