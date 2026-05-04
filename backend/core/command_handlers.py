"""Wykonanie wbudowanych komend — COMMANDS_SPEC §5."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, MutableMapping, Protocol


@dataclass
class CommandExecutionResult:
    success: bool
    message: str | None = None
    emotion: str | None = None
    side_effects: List[str] = field(default_factory=list)


class OrchestratorContext(Protocol):
    state: MutableMapping[str, Any]

    async def emit_side_effect(self, name: str, payload: Dict[str, Any]) -> None: ...


HandlerFn = Callable[[OrchestratorContext, Dict[str, str]], Awaitable[CommandExecutionResult]]

_builtin_registry: Dict[str, HandlerFn] = {}


def register_builtin(name: str, fn: HandlerFn) -> None:
    _builtin_registry[name] = fn


async def dispatch_builtin(action: str, ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    fn = _builtin_registry.get(action)
    if fn is None:
        return CommandExecutionResult(
            success=False,
            message=f"Brak handlera dla akcji {action!r}.",
            emotion="thinking",
        )
    return await fn(ctx, params)


async def sleep_handler(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    ctx.state["sleeping"] = True
    ctx.state["observer_paused"] = True
    await ctx.emit_side_effect("observer_pause", {})
    await ctx.emit_side_effect("avatar_hide", {})
    return CommandExecutionResult(success=True, message="Dobranoc. Śpij spokojnie.", emotion="sympathetic")


async def wake_handler(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    ctx.state["sleeping"] = False
    ctx.state["observer_paused"] = False
    await ctx.emit_side_effect("avatar_show", {})
    return CommandExecutionResult(success=True, message="O, wróciłeś! Co robimy?", emotion="excited")


async def observer_start_handler(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    ctx.state["observer_active"] = True
    ctx.state["observer_paused"] = False
    await ctx.emit_side_effect("observer_start", {})
    return CommandExecutionResult(success=True, message="Zaczynam obserwować.", emotion="excited")


async def observer_stop_handler(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    ctx.state["observer_active"] = False
    ctx.state["manual_game_profile_lock"] = False
    await ctx.emit_side_effect("observer_stop", {})
    return CommandExecutionResult(success=True, message="Już nie patrzę na grę.", emotion="neutral")


async def manual_game_set_handler(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    gid = (params.get("game_id") or "").strip().lower()
    if not gid:
        return CommandExecutionResult(
            success=False,
            message="Podaj identyfikator profilu gry, np. stellaris.",
            emotion="confused",
        )
    ctx.state["manual_game_profile_id"] = gid
    ctx.state["manual_game_profile_lock"] = True
    await ctx.emit_side_effect("manual_game_set", {"game_id": gid})
    return CommandExecutionResult(
        success=True,
        message=f"Ustawiono ręczny profil gry `{gid}`. Wykrywanie z procesów wstrzymane do resetu.",
        emotion="thinking",
    )


async def manual_game_clear_handler(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    ctx.state["manual_game_profile_lock"] = False
    ctx.state.pop("manual_game_profile_id", None)
    await ctx.emit_side_effect("manual_game_clear", {})
    return CommandExecutionResult(
        success=True,
        message="Z powrotem automatyczne wykrywanie gry z procesów.",
        emotion="neutral",
    )


async def silent_mode_on_handler(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    ctx.state["silent_mode"] = True
    await ctx.emit_side_effect("silent_mode", {"enabled": True})
    return CommandExecutionResult(success=True, message="Już ciszej.", emotion="thinking")


async def silent_mode_off_handler(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    ctx.state["silent_mode"] = False
    await ctx.emit_side_effect("silent_mode", {"enabled": False})
    return CommandExecutionResult(success=True, message="Znów mogę gadać!", emotion="happy")


async def backup_handler(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    await ctx.emit_side_effect("backup_request", {})
    return CommandExecutionResult(success=True, message="Zapisuję kopię zapasową w tle.", emotion="thinking")


async def session_report_stub(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    return CommandExecutionResult(
        success=True,
        message="Nie mam jeszcze pełnego raportu sesji podłączonego do bazy.",
        emotion="thinking",
    )


async def open_documents_handler(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    await ctx.emit_side_effect("open_documents", {})
    return CommandExecutionResult(success=True, message="Otwieram folder dokumentów.", emotion="thinking")


async def reload_config_stub(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    await ctx.emit_side_effect("reload_config", {})
    return CommandExecutionResult(success=True, message="Konfiguracja przeładowana.", emotion="thinking")


async def set_interval_handler(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    raw = params.get("n")
    try:
        n = int(raw) if raw is not None else 0
    except ValueError:
        return CommandExecutionResult(success=False, message="Podałeś nieprawidłowy interwał.", emotion="confused")
    n = max(5, min(300, n))
    ctx.state["observer_interval_seconds"] = n
    await ctx.emit_side_effect("observer_interval_changed", {"seconds": n})
    return CommandExecutionResult(success=True, message=f"W porządku, co {n} sekund.", emotion="thinking")


async def change_persona_handler(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    name = (params.get("name") or "").strip()
    ctx.state["active_persona"] = name.lower()
    return CommandExecutionResult(
        success=True,
        message=f"Przełączam personę na {name}.",
        emotion="thinking",
    )


async def change_character_handler(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    char_name = (params.get("char") or "").strip()
    ctx.state["active_character"] = char_name
    return CommandExecutionResult(
        success=True,
        message=f"Zapisuję że grasz jako {char_name}.",
        emotion="happy",
    )


async def click_through_on_handler(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    await ctx.emit_side_effect("window_click_through_on", {})
    return CommandExecutionResult(success=True, message="Masz plac do klikania.", emotion="thinking")


async def click_through_off_handler(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    await ctx.emit_side_effect("window_click_through_off", {})
    return CommandExecutionResult(success=True, message="Znów jestem ponad grą.", emotion="thinking")


async def forget_cache_stub(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    await ctx.emit_side_effect("mcp_cache_invalidate_all", {})
    return CommandExecutionResult(success=True, message="Czyszczę cache MCP.", emotion="thinking")


def install_default_builtin_handlers() -> None:
    register_builtin("sleep", sleep_handler)
    register_builtin("wake", wake_handler)
    register_builtin("observer_start", observer_start_handler)
    register_builtin("observer_stop", observer_stop_handler)
    register_builtin("manual_game_set", manual_game_set_handler)
    register_builtin("manual_game_clear", manual_game_clear_handler)
    register_builtin("silent_mode_on", silent_mode_on_handler)
    register_builtin("silent_mode_off", silent_mode_off_handler)
    register_builtin("backup", backup_handler)
    register_builtin("session_report", session_report_stub)
    register_builtin("open_documents", open_documents_handler)
    register_builtin("reload_config", reload_config_stub)
    register_builtin("set_interval", set_interval_handler)
    register_builtin("change_persona", change_persona_handler)
    register_builtin("change_character", change_character_handler)
    register_builtin("click_through_on", click_through_on_handler)
    register_builtin("click_through_off", click_through_off_handler)
    register_builtin("forget_cache", forget_cache_stub)


install_default_builtin_handlers()


__all__ = [
    "CommandExecutionResult",
    "OrchestratorContext",
    "dispatch_builtin",
    "register_builtin",
    "install_default_builtin_handlers",
]
