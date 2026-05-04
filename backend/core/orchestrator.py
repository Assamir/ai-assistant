"""Orkiestrator: komendy przed LLM, function calling z limitem narzędzi."""

from __future__ import annotations

import json as _json
import time
from enum import Enum
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Mapping, MutableMapping, Optional, Sequence

from backend.ai.llm_client import ChatCompletionResult, LMStudioClient
from backend.config.schema import ConfigSchema
from backend.core.command_handlers import CommandExecutionResult, OrchestratorContext, dispatch_builtin
from backend.core.command_matching import CommandMatcher, CooldownTracker
from backend.core.emotion_parser import parse_emotion_tag, resolve_default_emotion
from backend.core.persona_loader import LoadedPersona, PersonaLoader
from backend.core.prompt_builder import PromptBuilder
from backend.mcp.registry import ToolRegistry, _openai_tool_name
from backend.memory.semantic_recall import SemanticRecall


class OrchestratorState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


EmitFn = Callable[[str, Mapping[str, Any]], Awaitable[None]]


def _openai_tool_input_json(blob: Mapping[str, Any]) -> str:
    fn = blob.get("function") if isinstance(blob, dict) else None
    if not isinstance(fn, dict):
        return "{}"
    rv = fn.get("arguments")
    if isinstance(rv, str):
        return rv
    try:
        return _json.dumps(rv or {}, ensure_ascii=False)
    except (TypeError, ValueError):
        return "{}"


def _tool_payload_success(content: str) -> tuple[bool, Optional[str]]:
    try:
        obj = _json.loads(content)
        if isinstance(obj, dict) and obj.get("ok") is False:
            return False, (str(obj.get("error", ""))[:2000] or "tool_error")
        if isinstance(obj, dict) and obj.get("error") in ("rate_limited", "offline"):
            return False, str(obj.get("error", ""))
        return True, None
    except _json.JSONDecodeError:
        return True, None


class SimpleOrchestratorContext:
    """Minimalny kontekst dla handlerów komend."""

    __slots__ = ("_emitter", "_state")

    def __init__(self, state: MutableMapping[str, Any], emitter: EmitFn | None):
        self._state = state
        self._emitter = emitter

    @property
    def state(self) -> MutableMapping[str, Any]:
        return self._state

    async def emit_side_effect(self, name: str, payload: Dict[str, Any]) -> None:
        if self._emitter:
            await self._emitter(name, payload)


class ConversationOrchestrator:
    """Priorytet użytkownika: deterministic commands → optional MCP custom → LLM."""

    def __init__(
        self,
        *,
        configuration: ConfigSchema,
        lm_client: LMStudioClient,
        prompt_builder: PromptBuilder,
        persona_loader: PersonaLoader,
        command_matcher: CommandMatcher,
        tool_registry: ToolRegistry,
        active_persona: str = "default",
        emitter: EmitFn | None = None,
        db_path: Optional[str] = None,
        semantic_recall: Optional[SemanticRecall] = None,
        player_profile_repo: Optional[Any] = None,
    ) -> None:
        self._cfg = configuration
        self._llm = lm_client
        self._pb = prompt_builder
        self._personas = persona_loader
        self._matcher = command_matcher
        self._registry = tool_registry
        self._cooldown = CooldownTracker()
        self.phase = OrchestratorState.IDLE
        self.state: Dict[str, Any] = {"active_persona": active_persona, "online": True}
        self._emit = emitter
        self._max_tools = configuration.ai_runtime.max_tool_calls_per_turn
        self._db_path = db_path
        self._semantic_recall = semantic_recall
        self._player_profile_repo = player_profile_repo

    def apply_configuration(
        self,
        configuration: ConfigSchema,
        *,
        command_matcher: Optional[CommandMatcher] = None,
        persona_loader: Optional[PersonaLoader] = None,
    ) -> None:
        self._cfg = configuration
        if command_matcher is not None:
            self._matcher = command_matcher
        if persona_loader is not None:
            self._personas = persona_loader
        self._max_tools = configuration.ai_runtime.max_tool_calls_per_turn

    async def emit_visual_state(self, state_name: OrchestratorState) -> None:
        if self._emit:
            await self._emit("visual_state", {"state": state_name.value})

    def _resolve_persona(self) -> LoadedPersona:
        name = self.state.get("active_persona", "default")
        if isinstance(name, str):
            pname = name
        else:
            pname = "default"
        try:
            return self._personas.load(pname)
        except (OSError, ValueError):
            return self._personas.default_body_if_missing(pname)

    async def run_commands_if_any(
        self,
        text: str,
        *,
        emitter_override: EmitFn | None = None,
    ) -> Optional[list[CommandExecutionResult]]:
        emitter = emitter_override or self._emit
        ctx = SimpleOrchestratorContext(self.state, emitter)
        matched = self._matcher.match_all_segments(text)
        outcomes: List[CommandExecutionResult] = []

        if not matched:
            return None

        for mm in matched:
            if mm.tool_name:
                if not self._cooldown.can_execute(mm.cmd_id, mm.cooldown_seconds):
                    outcomes.append(
                        CommandExecutionResult(
                            success=False,
                            message=f"Za wcześnie — spróbuj za {mm.cooldown_seconds} sekund.",
                            emotion="thinking",
                        )
                    )
                    continue

                params: Dict[str, Any] = {"city": mm.params.get("city", "")}
                try:
                    tool_out = await self._registry.invoke(mm.tool_name, params, system_state=self.state)
                    self._cooldown.mark_executed(mm.cmd_id)
                    outcomes.append(
                        CommandExecutionResult(
                            success=True,
                            message=_json.dumps(tool_out, ensure_ascii=False)
                            if not isinstance(tool_out, str)
                            else tool_out,
                            emotion="thinking",
                        )
                    )
                except KeyError:
                    outcomes.append(
                        CommandExecutionResult(
                            success=False,
                            message=f"Narzędzie {mm.tool_name!r} nie jest zarejestrowane.",
                            emotion="thinking",
                        )
                    )
                continue

            if not mm.builtin_action:
                continue
            if not self._cooldown.can_execute(mm.cmd_id, mm.cooldown_seconds):
                outcomes.append(
                    CommandExecutionResult(
                        success=False,
                        message=f"Za wcześnie na tę akcję ({mm.cmd_id}), spróbuj później.",
                        emotion="thinking",
                    )
                )
                continue
            res = await dispatch_builtin(mm.builtin_action, ctx, mm.params or {})
            if res.success:
                self._cooldown.mark_executed(mm.cmd_id)
            outcomes.append(res)

        return outcomes or None

    async def run_llm_with_tools(
        self,
        user_text: str,
        *,
        conversation_tail: Sequence[Dict[str, Any]] = (),
        db_chat_session_id: Optional[int] = None,
    ) -> ChatCompletionResult:
        self.phase = OrchestratorState.THINKING
        await self.emit_visual_state(self.phase)
        persona = self._resolve_persona()
        tools_payload = self._registry.openai_tools()

        current_game = self.state.get("current_game")
        obs_ctx = f"Aktualnie wykryta gra: {current_game}." if current_game else None

        pp_summary: Optional[str] = None
        if self._player_profile_repo is not None:
            gid = self.state.get("current_game")
            pp_summary = self._player_profile_repo.summary_for_game(gid if isinstance(gid, str) else None)

        msgs: List[Dict[str, Any]] = self._pb.build_messages(
            assistant_name=self._cfg.general.assistant_name,
            content_root=str(self._cfg.general.content_root),
            persona_body_markdown=persona.body_markdown,
            history_messages=list(conversation_tail),
            max_context_tokens=self._cfg.ai_runtime.max_context_tokens,
            observer_context=obs_ctx,
            player_profile_summary=pp_summary,
        )
        if self._semantic_recall is not None and self._cfg.memory.inject_into_prompt:
            k = self._cfg.memory.recall_top_k
            kb_snippets = self._semantic_recall.recall_knowledge(user_text.strip(), k=max(1, min(k, 12)))
            if kb_snippets:
                block = "\n\n---\n\n".join(s.strip() for s in kb_snippets if str(s).strip())
                if block:
                    msgs.append(
                        {
                            "role": "system",
                            "content": (
                                "[Baza wiedzy — fragmenty z plików użytkownika; mogą być niekompletne.]\n" + block
                            ),
                        }
                    )
        msgs.append({"role": "user", "content": user_text})

        tool_calls_done = 0
        max_rounds = max(24, self._max_tools * 8)

        try:
            for _ in range(max_rounds):
                res = await self._llm.chat_completion(msgs, tools=tools_payload or None)
                tc_list_raw = res.tool_calls if isinstance(res.tool_calls, list) else []

                if not tc_list_raw:
                    return res

                msgs.append({"role": "assistant", "content": res.content or "", "tool_calls": tc_list_raw})

                parent_msg_id: Optional[int] = None
                if self._db_path and db_chat_session_id is not None:
                    from backend.db.repositories import MessageRepository

                    log_body = (res.content or "").strip() or "[wywołania narzędzi]"
                    parent_msg_id = await MessageRepository(self._db_path).create_message(
                        db_chat_session_id,
                        "assistant",
                        log_body,
                    )

                invoke_budget = max(0, self._max_tools - tool_calls_done)

                non_doc_calls = [
                    b
                    for b in tc_list_raw
                    if isinstance(b, dict) and _openai_tool_name(b) not in ("", "generate_document")
                ]
                if len(non_doc_calls) > invoke_budget:
                    msgs.append(
                        {
                            "role": "system",
                            "content": (
                                "[UWAGA] Osiągnięto limit narzędzi na tę turę — część wywołań została pominięta."
                            ),
                        }
                    )

                scheduled: List[Dict[str, Any]] = []
                non_doc_used = 0
                for blob in tc_list_raw:
                    if not isinstance(blob, dict):
                        continue
                    nm = _openai_tool_name(blob)
                    if nm == "generate_document":
                        scheduled.append(blob)
                        continue
                    if non_doc_used < invoke_budget:
                        scheduled.append(blob)
                        non_doc_used += 1

                turn_seq = 0
                for blob in scheduled:
                    if not isinstance(blob, dict):
                        continue
                    nm = _openai_tool_name(blob)
                    if nm != "generate_document":
                        tool_calls_done += 1
                    in_json = _openai_tool_input_json(blob)
                    t0 = time.perf_counter()
                    tool_msg: Optional[Dict[str, Any]] = None
                    try:
                        tool_msg = await self._registry.invoke_openai_tool_call(blob, system_state=self.state)
                        entry: Dict[str, Any] = {
                            "role": "tool",
                            "tool_call_id": tool_msg["tool_call_id"],
                            "content": tool_msg["content"],
                        }
                        tnm = tool_msg.get("name")
                        if tnm:
                            entry["name"] = tnm
                        msgs.append(entry)
                    except KeyError:
                        tc_id = blob.get("id")
                        tool_msg = {
                            "tool_call_id": tc_id if isinstance(tc_id, str) else "",
                            "name": nm,
                            "content": _json.dumps({"error": "unknown_tool"}, ensure_ascii=False),
                        }
                        msgs.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_msg["tool_call_id"],
                                "content": tool_msg["content"],
                            }
                        )
                    finally:
                        if parent_msg_id is not None and self._db_path:
                            turn_seq += 1
                            duration_ms = int((time.perf_counter() - t0) * 1000)
                            payload = (tool_msg or {}).get("content", "") if tool_msg else ""
                            log_nm = (tool_msg or {}).get("name") or nm or "unknown"
                            succ, err_note = _tool_payload_success(str(payload))
                            from backend.db.repositories import ToolCallsRepository

                            await ToolCallsRepository(self._db_path).insert_completed(
                                parent_msg_id,
                                turn_seq,
                                str(log_nm),
                                in_json,
                                str(payload) if payload else None,
                                duration_ms,
                                succ,
                                error_message=None if succ else err_note,
                            )

            msgs.append({"role": "system", "content": "[UWAGA] Za dużo rund narzędzi — przerywam z bezpieczeństwa."})
            return await self._llm.chat_completion(msgs, tools=None)
        finally:
            self.phase = OrchestratorState.IDLE
            await self.emit_visual_state(self.phase)

    async def handle_user_message(
        self,
        user_text: str,
        *,
        conversation_tail: Sequence[Dict[str, Any]] = (),
        persona_bias_fallback: Optional[str] = None,
        system_health: str = "healthy",
        emitter_override: EmitFn | None = None,
        db_chat_session_id: Optional[int] = None,
    ) -> CommandExecutionResult:
        cmds = await self.run_commands_if_any(user_text, emitter_override=emitter_override)
        if cmds:
            msgs = [c.message for c in cmds if c.message]
            merged = "\n".join(msgs).strip()
            emotion = cmds[-1].emotion or "neutral"
            self.phase = OrchestratorState.SPEAKING
            await self.emit_visual_state(self.phase)
            self.phase = OrchestratorState.IDLE
            return CommandExecutionResult(success=True, message=merged or "(brak odpowiedzi)", emotion=emotion)

        res = await self.run_llm_with_tools(
            user_text,
            conversation_tail=conversation_tail,
            db_chat_session_id=db_chat_session_id,
        )
        persona = self._resolve_persona()
        bias = persona_bias_fallback or persona.frontmatter.tts_emotion_bias
        emotion_tag, stripped = parse_emotion_tag(res.content or "")
        final_emotion = resolve_default_emotion(emotion_tag, bias, system_health)

        reply_text = stripped or res.content or ""
        return CommandExecutionResult(
            success=True,
            message=reply_text.strip(),
            emotion=final_emotion,
        )

    async def stream_reply_tokens(self, prompt: str, *, history_tail: Sequence[Dict[str, Any]] = ()) -> AsyncIterator[str]:
        """Passthrough stream LLM dla endpointów SSE (bez narzędzi w ścieżce streamu MVP)."""

        self.phase = OrchestratorState.THINKING
        await self.emit_visual_state(self.phase)
        try:
            async for chunk in self._llm.stream_response(prompt, list(history_tail), tools=None):
                yield chunk
        finally:
            self.phase = OrchestratorState.IDLE
            await self.emit_visual_state(self.phase)


__all__ = ["ConversationOrchestrator", "OrchestratorState", "SimpleOrchestratorContext"]
