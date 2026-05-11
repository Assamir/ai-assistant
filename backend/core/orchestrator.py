"""Orkiestrator: komendy przed LLM, wątki konwersacji, tryb agentowy, function calling."""

from __future__ import annotations

import json as _json
import time
from enum import Enum
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Mapping, MutableMapping, Optional, Sequence

from backend.ai.llm_client import ChatCompletionResult, LMStudioClient
from backend.config.schema import ConfigSchema
from backend.core.command_handlers import CommandExecutionResult, dispatch_builtin
from backend.core.command_matching import CommandMatcher, CooldownTracker
from backend.core.complexity_classifier import ComplexityClassifier
from backend.core.emotion_parser import parse_emotion_tag, resolve_default_emotion
from backend.core.persona_loader import LoadedPersona, PersonaLoader
from backend.core.prompt_builder import PromptBuilder
from backend.core.thread_manager import ThreadManager
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


def _append_tool_message_with_optional_user_mirror(
    msgs: List[Dict[str, Any]],
    *,
    entry: Dict[str, Any],
    fallback_tool_name: str,
    mirror_enabled: bool,
) -> None:
    """Wstawia `role=tool`; przy `mirror_enabled` duplikuje treść jako `user` (słaba obsługa FC w LM Studio)."""
    msgs.append(entry)
    if not mirror_enabled:
        return
    tname = (str(entry.get("name") or fallback_tool_name or "narzędzie") or "narzędzie").strip()
    tid = str(entry.get("tool_call_id") or "").strip()
    tcontent = str(entry.get("content") or "")
    header = f"[Wynik narzędzia `{tname}`"
    if tid:
        header += f", tool_call_id={tid}"
    header += " — uwzględnij to w odpowiedzi użytkownikowi po polsku.]\n"
    msgs.append({"role": "user", "content": header + tcontent})


def _build_agent_plan_block(state: MutableMapping[str, Any]) -> Optional[str]:
    plan = state.get("agent_plan")
    if not plan or not isinstance(plan, list):
        return None
    goal = state.get("agent_goal", "")
    lines = [f"Cel: {goal}" if goal else "Plan agentowy:"]
    status_icons = {"pending": "○", "in_progress": "▶", "done": "✓", "failed": "✗", "skipped": "—"}
    for step in plan:
        icon = status_icons.get(step.get("status", "pending"), "○")
        desc = step.get("description", "")
        result = step.get("result")
        line = f"{icon} Krok {step.get('index', 0) + 1}: {desc}"
        if result:
            line += f" → {result[:60]}"
        lines.append(line)
    return "\n".join(lines)


class SimpleOrchestratorContext:
    """Minimalny kontekst dla handlerów komend."""

    __slots__ = ("_emitter", "_state", "_services")

    def __init__(
        self,
        state: MutableMapping[str, Any],
        emitter: EmitFn | None,
        *,
        services: Optional[Dict[str, Any]] = None,
    ):
        self._state = state
        self._emitter = emitter
        self._services: Dict[str, Any] = services or {}

    @property
    def state(self) -> MutableMapping[str, Any]:
        return self._state

    def svc(self, name: str, default: Any = None) -> Any:
        return self._services.get(name, default)

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
        self._complexity_clf = ComplexityClassifier()
        self._thread_manager: Optional[ThreadManager] = ThreadManager(db_path) if db_path else None
        # Opcjonalne callables ustawiane przez app_context po wiring (unikamy circular dep)
        self._league_hint_fn: Optional[Any] = None
        self._daily_check_fn: Optional[Any] = None
        self._import_build_fn: Optional[Any] = None

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
        pname = name if isinstance(name, str) else "default"
        try:
            return self._personas.load(pname)
        except (OSError, ValueError):
            return self._personas.default_body_if_missing(pname)

    async def _handle_thread_for_message(
        self,
        user_text: str,
        message_id: Optional[int],
        emit: EmitFn | None,
    ) -> None:
        if not self._thread_manager or not self._cfg.threads.enabled:
            return
        active_thread_id = self.state.get("active_thread_id")
        try:
            result, thread_id = await self._thread_manager.handle_message(
                user_text,
                active_thread_id=active_thread_id if isinstance(active_thread_id, int) else None,
                message_id=message_id,
            )
            self.state["active_thread_id"] = thread_id
            if emit:
                if result.kind == "new":
                    await emit("thread_new", {"thread_id": thread_id, "title": None})
                elif result.kind == "resumed":
                    ctx = await self._thread_manager.get_context(thread_id, kind="resumed")
                    days_ago = 0
                    await emit("thread_resumed", {
                        "thread_id": thread_id,
                        "title": ctx.title if ctx else None,
                        "days_ago": days_ago,
                    })
                else:
                    ctx = await self._thread_manager.get_context(thread_id)
                    if ctx and ctx.title:
                        await emit("thread_continued", {
                            "thread_id": thread_id,
                            "title": ctx.title,
                        })
        except Exception:
            pass

    async def run_commands_if_any(
        self,
        text: str,
        *,
        emitter_override: EmitFn | None = None,
        db_chat_session_id: Optional[int] = None,
    ) -> Optional[list[CommandExecutionResult]]:
        emitter = emitter_override or self._emit
        services: Dict[str, Any] = {
            "league_hint_fn": self._league_hint_fn,
            "daily_check_fn": self._daily_check_fn,
            "import_build_fn": self._import_build_fn,
            "db_path": self._db_path,
            "db_session_id": db_chat_session_id,
            "semantic_recall": self._semantic_recall,
        }
        ctx = SimpleOrchestratorContext(self.state, emitter, services=services)
        matched = self._matcher.match_all_segments(text)
        outcomes: List[CommandExecutionResult] = []

        if not matched:
            return None

        for mm in matched:
            if mm.tool_name:
                if not self._cooldown.can_execute(mm.cmd_id, mm.cooldown_seconds):
                    outcomes.append(CommandExecutionResult(
                        success=False,
                        message=f"Za wcześnie — spróbuj za {mm.cooldown_seconds} sekund.",
                        emotion="thinking",
                    ))
                    continue

                params: Dict[str, Any] = {"city": mm.params.get("city", "")}
                try:
                    tool_out = await self._registry.invoke(mm.tool_name, params, system_state=self.state)
                    self._cooldown.mark_executed(mm.cmd_id)
                    outcomes.append(CommandExecutionResult(
                        success=True,
                        message=_json.dumps(tool_out, ensure_ascii=False) if not isinstance(tool_out, str) else tool_out,
                        emotion="thinking",
                    ))
                except KeyError:
                    outcomes.append(CommandExecutionResult(
                        success=False,
                        message=f"Narzędzie {mm.tool_name!r} nie jest zarejestrowane.",
                        emotion="thinking",
                    ))
                continue

            if not mm.builtin_action:
                continue
            if not self._cooldown.can_execute(mm.cmd_id, mm.cooldown_seconds):
                outcomes.append(CommandExecutionResult(
                    success=False,
                    message=f"Za wcześnie na tę akcję ({mm.cmd_id}), spróbuj później.",
                    emotion="thinking",
                ))
                continue
            res = await dispatch_builtin(mm.builtin_action, ctx, mm.params or {})
            if res.success:
                self._cooldown.mark_executed(mm.cmd_id)
            outcomes.append(res)

        return outcomes or None

    def _is_agentic_request(self, text: str) -> bool:
        mode = self._cfg.ai_runtime.agentic_complexity_mode
        if mode == "always":
            return True
        if mode == "never":
            return False
        return self._complexity_clf.classify(text) == "complex"

    def _build_thread_context_block(self) -> Optional[str]:
        thread_id = self.state.get("active_thread_id")
        if not isinstance(thread_id, int) or not self._thread_manager:
            return None
        ctx = self.state.get("_thread_context_cache")
        if not ctx:
            return None
        if hasattr(ctx, "to_prompt_block"):
            count = self.state.get("_thread_message_count", 0)
            return ctx.to_prompt_block(count)
        return None

    async def _load_thread_context_into_state(self, thread_id: int) -> None:
        if not self._thread_manager:
            return
        try:
            ctx = await self._thread_manager.get_context(thread_id)
            self.state["_thread_context_cache"] = ctx
        except Exception:
            pass

    async def run_llm_with_tools(
        self,
        user_text: str,
        *,
        conversation_tail: Sequence[Dict[str, Any]] = (),
        db_chat_session_id: Optional[int] = None,
        emitter_override: EmitFn | None = None,
    ) -> ChatCompletionResult:
        emit = emitter_override or self._emit

        agentic = (
            self._cfg.ai_runtime.agentic_mode_enabled
            and self._is_agentic_request(user_text)
        )

        if agentic:
            return await self._run_agentic_loop(
                user_text,
                conversation_tail=conversation_tail,
                db_chat_session_id=db_chat_session_id,
                emit=emit,
            )
        return await self._run_standard_loop(
            user_text,
            conversation_tail=conversation_tail,
            db_chat_session_id=db_chat_session_id,
            emit=emit,
        )

    async def _build_messages(
        self,
        user_text: str,
        conversation_tail: Sequence[Dict[str, Any]],
        max_context_tokens: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        persona = self._resolve_persona()
        current_game = self.state.get("current_game")
        obs_ctx = f"Aktualnie wykryta gra: {current_game}." if current_game else None

        pp_summary: Optional[str] = None
        if self._player_profile_repo is not None:
            gid = self.state.get("current_game")
            pp_summary = self._player_profile_repo.summary_for_game(gid if isinstance(gid, str) else None)

        thread_id = self.state.get("active_thread_id")
        if isinstance(thread_id, int):
            await self._load_thread_context_into_state(thread_id)
        thread_block = self._build_thread_context_block()
        agent_plan_block = _build_agent_plan_block(self.state)

        msgs: List[Dict[str, Any]] = self._pb.build_messages(
            assistant_name=self._cfg.general.assistant_name,
            content_root=str(self._cfg.general.content_root),
            persona_body_markdown=persona.body_markdown,
            history_messages=list(conversation_tail),
            max_context_tokens=max_context_tokens or self._cfg.ai_runtime.max_context_tokens,
            observer_context=obs_ctx,
            player_profile_summary=pp_summary,
            thread_context_block=thread_block,
            agent_plan_block=agent_plan_block,
        )

        if self._semantic_recall is not None and self._cfg.memory.inject_into_prompt:
            k = self._cfg.memory.recall_top_k
            kb_snippets = self._semantic_recall.recall_knowledge(user_text.strip(), k=max(1, min(k, 12)))
            if kb_snippets:
                block = "\n\n---\n\n".join(s.strip() for s in kb_snippets if str(s).strip())
                if block:
                    msgs.append({
                        "role": "system",
                        "content": "[Baza wiedzy — fragmenty z plików użytkownika; mogą być niekompletne.]\n" + block,
                    })

        msgs.append({"role": "user", "content": user_text})
        return msgs

    async def _execute_tool_calls(
        self,
        msgs: List[Dict[str, Any]],
        tc_list_raw: List[Any],
        *,
        tool_calls_done: int,
        max_tools: int,
        parent_msg_id: Optional[int],
        emit: EmitFn | None,
        turn_offset: int = 0,
    ) -> int:
        invoke_budget = max(0, max_tools - tool_calls_done)
        _EXEMPT = ("", "generate_document", "plan_create", "plan_get", "task_start",
                   "task_done", "task_revise", "work_evaluate", "note_save", "notes_get",
                   "thread_add_decision", "thread_add_direction", "thread_summarize",
                   "thread_search", "thread_resume")

        non_budget_calls = [b for b in tc_list_raw if isinstance(b, dict) and _openai_tool_name(b) in _EXEMPT]
        budget_calls = [b for b in tc_list_raw if isinstance(b, dict) and _openai_tool_name(b) not in _EXEMPT]

        if len(budget_calls) > invoke_budget:
            msgs.append({"role": "system", "content": "[UWAGA] Osiągnięto limit narzędzi — część wywołań pominięta."})

        scheduled = non_budget_calls + budget_calls[:invoke_budget]
        used = len([b for b in budget_calls[:invoke_budget] if _openai_tool_name(b) not in _EXEMPT])

        turn_seq = turn_offset
        for blob in scheduled:
            if not isinstance(blob, dict):
                continue
            nm = _openai_tool_name(blob)
            in_json = _openai_tool_input_json(blob)
            preview = str(in_json)[:480]
            if nm and emit:
                await emit("agent_activity", {"phase": "tool_start", "tool": nm, "arguments_preview": preview})

            t0 = time.perf_counter()
            tool_msg: Optional[Dict[str, Any]] = None
            try:
                tool_msg = await self._registry.invoke_openai_tool_call(blob, system_state=self.state)
                entry: Dict[str, Any] = {
                    "role": "tool",
                    "tool_call_id": tool_msg["tool_call_id"],
                    "content": tool_msg["content"],
                }
                if tool_msg.get("name"):
                    entry["name"] = tool_msg["name"]
                _append_tool_message_with_optional_user_mirror(
                    msgs, entry=entry, fallback_tool_name=nm,
                    mirror_enabled=self._cfg.ai_runtime.mirror_tool_results_as_user,
                )

                if nm in ("plan_create",) and emit:
                    try:
                        parsed = _json.loads(tool_msg["content"])
                        if parsed.get("ok"):
                            await emit("agent_plan_created", {
                                "goal": parsed.get("goal", ""),
                                "steps": parsed.get("steps", []),
                            })
                    except Exception:
                        pass
                elif nm == "task_done" and emit:
                    try:
                        parsed = _json.loads(tool_msg["content"])
                        if parsed.get("ok"):
                            await emit("agent_step_done", {
                                "step_index": parsed.get("step_index"),
                                "result_summary": parsed.get("result", ""),
                            })
                    except Exception:
                        pass
                elif nm == "task_start" and emit:
                    try:
                        parsed = _json.loads(tool_msg["content"])
                        if parsed.get("ok"):
                            await emit("agent_step_started", {
                                "step_index": parsed.get("step_index"),
                                "description": parsed.get("description", ""),
                            })
                    except Exception:
                        pass
                elif nm == "task_revise" and emit:
                    try:
                        parsed = _json.loads(tool_msg["content"])
                        if parsed.get("ok"):
                            await emit("agent_plan_revised", {
                                "reason": parsed.get("reason", ""),
                                "revised_from_step": parsed.get("revised_from_step"),
                            })
                    except Exception:
                        pass
                elif nm == "thread_summarize" and emit:
                    try:
                        parsed = _json.loads(tool_msg["content"])
                        if parsed.get("ok"):
                            await emit("thread_summary_updated", {
                                "thread_id": self.state.get("active_thread_id"),
                                "title": parsed.get("title"),
                            })
                    except Exception:
                        pass

            except KeyError:
                tc_id = blob.get("id")
                tool_msg = {
                    "tool_call_id": tc_id if isinstance(tc_id, str) else "",
                    "name": nm,
                    "content": _json.dumps({"error": "unknown_tool"}, ensure_ascii=False),
                }
                entry_err: Dict[str, Any] = {
                    "role": "tool",
                    "tool_call_id": tool_msg["tool_call_id"],
                    "content": tool_msg["content"],
                }
                if nm:
                    entry_err["name"] = nm
                _append_tool_message_with_optional_user_mirror(
                    msgs, entry=entry_err, fallback_tool_name=nm,
                    mirror_enabled=self._cfg.ai_runtime.mirror_tool_results_as_user,
                )
            finally:
                if parent_msg_id is not None and self._db_path:
                    turn_seq += 1
                    capped_seq = min(turn_seq, 50)
                    duration_ms = int((time.perf_counter() - t0) * 1000)
                    payload = (tool_msg or {}).get("content", "") if tool_msg else ""
                    log_nm = (tool_msg or {}).get("name") or nm or "unknown"
                    succ, err_note = _tool_payload_success(str(payload))
                    from backend.db.repositories import ToolCallsRepository
                    await ToolCallsRepository(self._db_path).insert_completed(
                        parent_msg_id, capped_seq, str(log_nm), in_json,
                        str(payload) if payload else None, duration_ms, succ,
                        error_message=None if succ else err_note,
                    )

        return used

    async def _run_standard_loop(
        self,
        user_text: str,
        *,
        conversation_tail: Sequence[Dict[str, Any]],
        db_chat_session_id: Optional[int],
        emit: EmitFn | None,
    ) -> ChatCompletionResult:
        async def _vs(s: OrchestratorState) -> None:
            self.phase = s
            if emit:
                await emit("visual_state", {"state": s.value})

        await _vs(OrchestratorState.THINKING)
        tools_payload = self._registry.openai_tools()
        msgs = await self._build_messages(user_text, conversation_tail)

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
                        db_chat_session_id, "assistant", log_body,
                    )

                used = await self._execute_tool_calls(
                    msgs, tc_list_raw,
                    tool_calls_done=tool_calls_done,
                    max_tools=self._max_tools,
                    parent_msg_id=parent_msg_id,
                    emit=emit,
                )
                tool_calls_done += used

            msgs.append({"role": "system", "content": "[UWAGA] Za dużo rund narzędzi — przerywam z bezpieczeństwa."})
            return await self._llm.chat_completion(msgs, tools=None)
        finally:
            self.phase = OrchestratorState.IDLE
            if emit:
                await emit("visual_state", {"state": OrchestratorState.IDLE.value})

    async def _run_agentic_loop(
        self,
        user_text: str,
        *,
        conversation_tail: Sequence[Dict[str, Any]],
        db_chat_session_id: Optional[int],
        emit: EmitFn | None,
    ) -> ChatCompletionResult:
        async def _vs(s: OrchestratorState) -> None:
            self.phase = s
            if emit:
                await emit("visual_state", {"state": s.value})

        await _vs(OrchestratorState.THINKING)
        max_tools = self._cfg.ai_runtime.agentic_max_tool_calls
        tools_payload = self._registry.openai_tools()
        quality_threshold = self._cfg.ai_runtime.agentic_quality_threshold
        max_replan = self._cfg.ai_runtime.agentic_max_replan_rounds

        self.state.pop("agent_plan", None)
        self.state.pop("agent_goal", None)
        self.state.pop("agent_quality_score", None)
        self.state.pop("agent_notes_mem", None)
        self.state.pop("agent_task_ids", None)

        final_result: Optional[ChatCompletionResult] = None

        try:
            for replan_round in range(max_replan + 1):
                msgs = await self._build_messages(user_text, conversation_tail)
                tool_calls_done = 0
                max_rounds = max(40, max_tools * 4)

                for _ in range(max_rounds):
                    res = await self._llm.chat_completion(msgs, tools=tools_payload or None)
                    tc_list_raw = res.tool_calls if isinstance(res.tool_calls, list) else []

                    if not tc_list_raw:
                        final_result = res
                        break

                    msgs.append({"role": "assistant", "content": res.content or "", "tool_calls": tc_list_raw})

                    parent_msg_id: Optional[int] = None
                    if self._db_path and db_chat_session_id is not None:
                        from backend.db.repositories import MessageRepository
                        log_body = (res.content or "").strip() or "[wywołania narzędzi]"
                        parent_msg_id = await MessageRepository(self._db_path).create_message(
                            db_chat_session_id, "assistant", log_body,
                        )

                    used = await self._execute_tool_calls(
                        msgs, tc_list_raw,
                        tool_calls_done=tool_calls_done,
                        max_tools=max_tools,
                        parent_msg_id=parent_msg_id,
                        emit=emit,
                        turn_offset=tool_calls_done,
                    )
                    tool_calls_done += used
                else:
                    msgs.append({"role": "system", "content": "[UWAGA] Za dużo rund narzędzi — kończę."})
                    final_result = await self._llm.chat_completion(msgs, tools=None)

                quality_score = self.state.get("agent_quality_score")
                if quality_score is not None and float(quality_score) < quality_threshold:
                    if replan_round < max_replan:
                        issues = self.state.get("agent_evaluation_summary", "")
                        if emit:
                            await emit("agent_plan_revised", {
                                "reason": f"Niska jakość ({quality_score:.2f}) — ponawiam (runda {replan_round + 2}/{max_replan + 1})",
                                "revised_from_step": 0,
                            })
                        user_text = (
                            f"{user_text}\n\n[KONTEKST: Poprzednia próba miała niską jakość ({quality_score:.2f}). "
                            f"Problemy: {issues}. Spróbuj inaczej.]"
                        )
                        self.state.pop("agent_plan", None)
                        self.state.pop("agent_quality_score", None)
                        continue
                break

            score = self.state.get("agent_quality_score")
            if emit:
                await emit("agent_evaluation_done", {
                    "score": score,
                    "verdict": "cel osiągnięty" if (score is not None and float(score) >= quality_threshold) else "wynik niepełny",
                    "replanning": False,
                })

            return final_result or await self._llm.chat_completion(
                await self._build_messages(user_text, conversation_tail), tools=None
            )
        finally:
            self.phase = OrchestratorState.IDLE
            if emit:
                await emit("visual_state", {"state": OrchestratorState.IDLE.value})

    async def handle_user_message(
        self,
        user_text: str,
        *,
        conversation_tail: Sequence[Dict[str, Any]] = (),
        persona_bias_fallback: Optional[str] = None,
        system_health: str = "healthy",
        emitter_override: EmitFn | None = None,
        db_chat_session_id: Optional[int] = None,
        message_id: Optional[int] = None,
    ) -> CommandExecutionResult:
        emitter = emitter_override or self._emit

        if db_chat_session_id is not None:
            self.state["db_session_id"] = db_chat_session_id

        await self._handle_thread_for_message(user_text, message_id, emitter)

        cmds = await self.run_commands_if_any(
            user_text,
            emitter_override=emitter_override,
            db_chat_session_id=db_chat_session_id,
        )
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
            emitter_override=emitter_override,
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

    async def stream_reply_tokens(
        self,
        prompt: str,
        *,
        history_tail: Sequence[Dict[str, Any]] = (),
    ) -> AsyncIterator[str]:
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
