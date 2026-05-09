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


async def session_report_handler(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    db_path: Any = getattr(ctx, "svc", lambda n, d=None: d)("db_path")
    session_id: Any = getattr(ctx, "svc", lambda n, d=None: d)("db_session_id")
    if not db_path or session_id is None:
        return CommandExecutionResult(
            success=True,
            message="Brak aktywnej sesji w bazie — spróbuj przez interfejs graficzny.",
            emotion="thinking",
        )
    try:
        import aiosqlite
        from backend.db.connection import apply_pragmas_async

        async with aiosqlite.connect(db_path) as db:
            await apply_pragmas_async(db)
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT source, COUNT(*) as cnt FROM messages WHERE session_id=? GROUP BY source",
                (session_id,),
            )
            rows = await cur.fetchall()

        parts: List[str] = []
        total = 0
        for r in rows:
            source = r["source"]
            cnt = int(r["cnt"])
            total += cnt
            label = {"user": "twoje", "assistant": "moje", "observer": "obserwatora"}.get(source, source)
            parts.append(f"{cnt} {label}")
        summary = ", ".join(parts) if parts else "brak wiadomości"
        return CommandExecutionResult(
            success=True,
            message=f"W tej sesji było {total} wiadomości: {summary}.",
            emotion="thinking",
        )
    except Exception as exc:
        return CommandExecutionResult(
            success=False,
            message=f"Nie udało się pobrać raportu: {exc}",
            emotion="confused",
        )


async def check_league_hint_handler(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    svc = getattr(ctx, "svc", lambda n, d=None: d)
    league_hint_fn: Any = svc("league_hint_fn")
    game_id: str = (params.get("game_id") or ctx.state.get("current_game") or "").strip()
    if not game_id:
        return CommandExecutionResult(
            success=False,
            message="Nie wykryto aktywnej gry. Uruchom grę lub ustaw profil ręcznie.",
            emotion="confused",
        )
    if league_hint_fn is None:
        return CommandExecutionResult(
            success=False,
            message="Sprawdzanie hintów ligi jest niedostępne — brak profilu gracza lub wyszukiwarki.",
            emotion="confused",
        )
    try:
        out: Dict[str, Any] = await league_hint_fn(game_id)
    except Exception as exc:
        return CommandExecutionResult(success=False, message=f"Błąd sprawdzania ligi: {exc}", emotion="confused")
    if not out.get("ok"):
        err = out.get("error", "error")
        msg_map = {
            "game_not_in_profile": f"Gra {game_id!r} nie jest w profilu gracza.",
            "web_search_unavailable": "Wyszukiwarka jest wyłączona. Włącz MCP i narzędzie web_search.",
            "search_failed": "Wyszukiwanie nie powiodło się.",
        }
        return CommandExecutionResult(
            success=False,
            message=msg_map.get(str(err), f"Nie udało się sprawdzić ligi: {err}"),
            emotion="confused",
        )
    prof_league = out.get("profile_league") or "nieznana"
    if out.get("mismatch_hint"):
        return CommandExecutionResult(
            success=True,
            message=(
                f"Uwaga! W profilu masz ligę {prof_league!r}, ale wyniki wyszukiwania "
                f"sugerują że coś się zmieniło. Sprawdź aktualne informacje o {game_id}."
            ),
            emotion="excited",
        )
    return CommandExecutionResult(
        success=True,
        message=f"Liga {prof_league!r} w profilu wygląda aktualnie dla {game_id}.",
        emotion="happy",
    )


async def daily_check_handler(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    svc = getattr(ctx, "svc", lambda n, d=None: d)
    daily_check_fn: Any = svc("daily_check_fn")
    game_id: str = (params.get("game_id") or ctx.state.get("current_game") or "").strip()
    if not game_id:
        return CommandExecutionResult(
            success=False,
            message="Nie wykryto aktywnej gry. Uruchom grę lub ustaw profil ręcznie.",
            emotion="confused",
        )
    if daily_check_fn is None:
        return CommandExecutionResult(
            success=False,
            message="Daily check jest niedostępny — brak profilu gracza lub wyszukiwarki.",
            emotion="confused",
        )
    try:
        out: Dict[str, Any] = await daily_check_fn(game_id, False)
    except Exception as exc:
        return CommandExecutionResult(success=False, message=f"Błąd sprawdzania meta: {exc}", emotion="confused")
    if not out.get("ok"):
        err = out.get("error", "error")
        msg_map = {
            "game_not_in_profile": f"Gra {game_id!r} nie jest w profilu gracza.",
            "too_soon": "Sprawdzałam niedawno. Poczekaj trochę lub powiedz 'sprawdź meta teraz'.",
        }
        return CommandExecutionResult(
            success=False,
            message=msg_map.get(str(err), f"Nie udało się sprawdzić meta: {err}"),
            emotion="thinking",
        )
    has_changes = out.get("has_changes", False)
    if has_changes:
        return CommandExecutionResult(
            success=True,
            message=f"Są nowości w {game_id}! Zaktualizowałam bazę wiedzy. Możesz zapytać mnie o szczegóły.",
            emotion="excited",
        )
    return CommandExecutionResult(
        success=True,
        message=f"Sprawdziłam meta {game_id} — nic nowego od ostatniego razu.",
        emotion="neutral",
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


async def forget_knowledge_handler(ctx: OrchestratorContext, params: Dict[str, str]) -> CommandExecutionResult:
    topic = (params.get("topic") or "").strip().lower()
    if not topic:
        return CommandExecutionResult(success=False, message="Nie rozumiem — o czym mam zapomnieć?", emotion="confused")

    svc = getattr(ctx, "svc", lambda n, d=None: d)
    sr: Any = svc("semantic_recall")
    if sr is None:
        return CommandExecutionResult(
            success=False,
            message="Pamięć semantyczna jest wyłączona — nie mam czego zapominać.",
            emotion="thinking",
        )
    try:
        removed = sr.remove_knowledge_chunks_where({"source_path": f"{topic}.md"})
        if not removed:
            slug = topic.replace(" ", "_")
            removed = sr.remove_knowledge_chunks_where({"source_path": f"{slug}.md"})
        if removed:
            plural = "fragmenty" if removed > 1 else "fragment"
            return CommandExecutionResult(
                success=True,
                message=f"Usunelam {removed} {plural} wiedzy o '{topic}'. Zapomniane.",
                emotion="thinking",
            )
        return CommandExecutionResult(
            success=True,
            message=f"Nie znalazlam wiedzy o '{topic}' do usuniecia.",
            emotion="thinking",
        )
    except Exception as exc:
        return CommandExecutionResult(
            success=False,
            message=f"Błąd usuwania wiedzy: {exc}",
            emotion="confused",
        )


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
    register_builtin("session_report", session_report_handler)
    register_builtin("open_documents", open_documents_handler)
    register_builtin("reload_config", reload_config_stub)
    register_builtin("set_interval", set_interval_handler)
    register_builtin("change_persona", change_persona_handler)
    register_builtin("change_character", change_character_handler)
    register_builtin("click_through_on", click_through_on_handler)
    register_builtin("click_through_off", click_through_off_handler)
    register_builtin("forget_cache", forget_cache_stub)
    register_builtin("check_league_hint", check_league_hint_handler)
    register_builtin("daily_check", daily_check_handler)
    register_builtin("forget_knowledge", forget_knowledge_handler)


install_default_builtin_handlers()


__all__ = [
    "CommandExecutionResult",
    "OrchestratorContext",
    "dispatch_builtin",
    "register_builtin",
    "install_default_builtin_handlers",
    "check_league_hint_handler",
    "daily_check_handler",
    "session_report_handler",
]
