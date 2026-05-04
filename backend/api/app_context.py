"""Współdzielony stan HTTP/WS dla FastAPI."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.ai.llm_client import LMStudioClient
from backend.config.loader import ConfigLoader
from backend.config.schema import ConfigSchema
from backend.core.command_matching import CommandMatcher
from backend.core.interfaces import BaseSTTEngine, BaseTTSEngine
from backend.core.orchestrator import ConversationOrchestrator
from backend.core.persona_loader import PersonaLoader
from backend.core.prompt_builder import PromptBuilder
from backend.mcp.registry import ToolRegistry, build_default_tool_registry


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


@dataclass
class AppContext:

    config: ConfigSchema
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


def create_app_context() -> AppContext:
    cfg = ConfigLoader().load_config(None)
    personas_dir = Path(cfg.general.content_root).expanduser() / "personas"
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

    return AppContext(
        config=cfg,
        conversation=ConversationStore(),
        prompt_builder=pb,
        persona_loader=pl,
        tool_registry=reg,
        command_matcher=matcher,
        llm_client=llm,
        orchestrator=orch,
        websocket_manager=WebSocketManager(),
    )


__all__ = ["AppContext", "ConversationStore", "WebSocketManager", "create_app_context"]
