"""Orkiestrator: komendy przed LLM, function calling z limitem narzędzi."""

from __future__ import annotations

import json as _json
from enum import Enum
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Mapping, MutableMapping, Optional, Sequence

from backend.ai.llm_client import ChatCompletionResult, LMStudioClient
from backend.config.schema import ConfigSchema
from backend.core.command_handlers import CommandExecutionResult, OrchestratorContext, dispatch_builtin
from backend.core.command_matching import CommandMatcher, CooldownTracker
from backend.core.emotion_parser import parse_emotion_tag, resolve_default_emotion
from backend.core.persona_loader import LoadedPersona, PersonaLoader
from backend.core.prompt_builder import PromptBuilder
from backend.mcp.registry import ToolRegistry


class OrchestratorState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


EmitFn = Callable[[str, Mapping[str, Any]], Awaitable[None]]


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
    ) -> None:
        self._cfg = configuration
        self._llm = lm_client
        self._pb = prompt_builder
        self._personas = persona_loader
        self._matcher = command_matcher
        self._registry = tool_registry
        self._cooldown = CooldownTracker()
        self.phase = OrchestratorState.IDLE
        self.state: Dict[str, Any] = {"active_persona": active_persona}
        self._emit = emitter
        self._max_tools = configuration.ai_runtime.max_tool_calls_per_turn

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
                    tool_out = await self._registry.invoke(mm.tool_name, params)
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
    ) -> ChatCompletionResult:
        self.phase = OrchestratorState.THINKING
        await self.emit_visual_state(self.phase)
        persona = self._resolve_persona()
        tools_payload = self._registry.openai_tools()

        current_game = self.state.get("current_game")
        obs_ctx = f"Aktualnie wykryta gra: {current_game}." if current_game else None

        msgs: List[Dict[str, Any]] = self._pb.build_messages(
            assistant_name=self._cfg.general.assistant_name,
            content_root=str(self._cfg.general.content_root),
            persona_body_markdown=persona.body_markdown,
            history_messages=list(conversation_tail),
            max_context_tokens=self._cfg.ai_runtime.max_context_tokens,
            observer_context=obs_ctx,
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

                invoke_budget = max(0, self._max_tools - tool_calls_done)
                if invoke_budget <= 0:
                    msgs.append(
                        {
                            "role": "system",
                            "content": (
                                "[UWAGA] Osiągnięto limit narzędzi na tę turę — daj odpowiedź bez nowych wywołań narzędzi."
                            ),
                        }
                    )
                    continue

                for blob in tc_list_raw[:invoke_budget]:
                    if not isinstance(blob, dict):
                        continue
                    tool_calls_done += 1
                    try:
                        tool_msg = await self._registry.invoke_openai_tool_call(blob)
                        entry: Dict[str, Any] = {
                            "role": "tool",
                            "tool_call_id": tool_msg["tool_call_id"],
                            "content": tool_msg["content"],
                        }
                        nm = tool_msg.get("name")
                        if nm:
                            entry["name"] = nm
                        msgs.append(entry)
                    except KeyError:
                        tc_id = blob.get("id")
                        msgs.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc_id if isinstance(tc_id, str) else "",
                                "content": _json.dumps({"error": "unknown_tool"}, ensure_ascii=False),
                            }
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

        res = await self.run_llm_with_tools(user_text, conversation_tail=conversation_tail)
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
