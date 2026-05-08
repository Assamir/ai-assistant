"""Dopasowywanie komend systemowych — COMMANDS_SPEC §3–5."""

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Pattern, Sequence

COMMAND_CONFIDENCE_THRESHOLD = 0.75


def normalize(text: str) -> str:
    text = text.lower().strip()
    nfkd = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in nfkd if not unicodedata.combining(c))
    text = text.replace("ł", "l").replace("Ł", "l")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        return levenshtein(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            ins = cur[j - 1] + 1
            delete = prev[j] + 1
            repl = prev[j - 1] + (ca != cb)
            cur.append(min(ins, delete, repl))
        prev = cur
    return prev[-1]


def _anchor(p: str) -> Pattern[str]:
    return re.compile(r"^\s*" + p + r"\s*$", re.DOTALL)


_SLEEP_P = (
    r"(?!nie\s)(?:.*\b(?:idz\s+spac|wylacz\s+sie|dobranoc|uslij)\b.*|.*\bspij\b.*|"
    r".*\bgo\s+to\s+sleep\b.*|.*\bsleep\s+mode\b.*)"
)
_WAKE_P = r"(?:obudz\s+sie|wroc\b|hej\s+wroc|jestes\s+tu|wake\s+up|come\s+back)\b.*"
_SILENT_ON_P = (
    r".*\b(?:wycisz\s+sie|badz\s+cicho|tryb\s+cichy|\bnie\s+mow\b|\bbe\s+quiet\b|silent\s+mode\b)\b.*"
)
_SILENT_OFF_P = (
    r"(?:mozesz\s+mowic|mozna\s+mowic|mow\s+normalnie|wroc\s+do\s+mowienia\b|"
    r"koniec\s+ciszy\b|you\s+can\s+speak\b|unmute\b)(?:\s+.*)?$"
)
_CT_ON_P = r".*(?:pozwol\s+mi\s+klikac|idz\s+na\s+bok|nie\s+blokuj\s+myszy|click\s+through\s+on|let\s+me\s+click).*$"
_CT_OFF_P = r".*(?:wroc\s+na\s+wierzch\b|blokuj\s+klik|znowu\s+aktywny\b|click\s+through\s+off\b|block\s+clicks).*$"
obs_start_inner = (
    r"(?:zacznij\s+obserwowac\b|wlacz\s+obserwatora\b|patrz\s+na\s+gre\b|sledz\s+gre\b|"
    r"start\s+observing\b|watch\s+the\s+game\b|\bobserwuj\b(?:\s+\w+)*)"
)

obs_start_pat = rf"(?!nie\s)(?:{obs_start_inner})"
obs_stop = (
    r".*(?:przestan\s+obserwowac|wylacz\s+obserwatora\b|\bnie\s+obserwuj\b|stop\s+observing|stop\s+watching)\b.*$"
)
_INTERVAL_P = r"(?:ustaw|zmien)\s+(?:interwal|interval)\s+na\s+(?P<n>\d+)\s+sekund"
_PERSONA_P = r"(?:zmien\s+persone\s+na\s+(?P<name>[\w-]+)|badz\s+(?P<name_b>[\w-]+)|przelacz\s+na\s+persone\s+(?P<name_c>[\w-]+))"
_CHARACTER_P = r"(?:gram\s+teraz\s+(?P<char>.+)|jestem\s+teraz\s+(?P<char2>.+)|zmien\s+postac\s+na\s+(?P<char3>.+))"
_BACKUP_P = (
    r".*(?:zrob\s+backup\b|wykonaj\s+backup\b|kopia\s+zapasowa\b|make\s+backup\b|create\s+backup\b).*$"
)
_SESSION_REP_P = (
    r"(?:\bpodsumuj\b(?:\s+sesje)?(?:\s+.+)?|\braport\s+z\s+sesji\b.*|\bco\s+robilem\b.*|"
    r"summarize\s+session\b.*|session\s+report\b.*)"
)
_REL_CFG_P = r".*(?:przeladuj\s+konfiguracje\b|odswiez\s+config\b|zaladuj\s+ustawienia\s+ponownie\b|reload\s+config\b).*$"
_OPEN_DOC_P = r".*(?:otworz\s+dokumenty|pokaz\s+dokumenty|gdzie\s+sa\s+dokumenty).*$"
forget_p = (
    r".*(?:odswiez\s+informacje\b|zapomnij\s+cache\b|wyczysc\s+cache\b|refresh\s+info\b|\bclear\s+cache\b).*$"
)
_GAME_MANUAL_P = r"(?:ustaw|wybierz)\s+gre\s+(?:na\s+)?(?P<game_id>[\w-]+)\b"
_GAME_AUTO_P = (
    r".*(?:wykrywaj\s+gre\s+automatycznie|automatyczna\s+detekcja\s+gry|"
    r"clear\s+manual\s+game|resetuj\s+wybor\s+gry)\b.*$"
)
_LEAGUE_HINT_P = (
    r".*(?:sprawdz\s+hint\s+ligi\b|sprawdz\s+lige\b|sprawdz\s+aktualna\s+lige\b|"
    r"jaka\s+jest\s+aktualna\s+liga\b|sprawdz\s+czy\s+liga\s+sie\s+zmienila\b|"
    r"check\s+league\s+hint\b|league\s+hint\b).*$"
)
_DAILY_CHECK_P = (
    r".*(?:sprawdz\s+meta\b|sprawdz\s+meta\s+gry\b|co\s+nowego\s+w\s+grze\b|"
    r"co\s+sie\s+zmienilo\s+w\s+grze\b|sprawdz\s+zmiany\s+w\s+grze\b|"
    r"check\s+game\s+meta\b|sprawdz\s+meta\s+teraz\b).*$"
)


@dataclass(frozen=True)
class BuiltinMatchRule:
    cmd_id: str
    priority: int
    builtin_action: str
    pattern: Pattern[str]
    cooldown_seconds: int = 0


@dataclass(frozen=True)
class CustomMatchRule:
    cmd_id: str
    priority: int
    pattern: Pattern[str]
    tool_name: str
    cooldown_seconds: int = 0


@dataclass
class CommandMatch:
    cmd_id: str
    builtin_action: Optional[str]
    params: Dict[str, str]
    confidence: float
    cooldown_seconds: int = 0
    tool_name: Optional[str] = None


class CooldownTracker:
    def __init__(self) -> None:
        self._last: Dict[str, float] = {}

    def can_execute(self, cmd_id: str, cooldown_seconds: int) -> bool:
        last = self._last.get(cmd_id, 0.0)
        return (time.monotonic() - last) >= float(cooldown_seconds)

    def mark_executed(self, cmd_id: str) -> None:
        self._last[cmd_id] = time.monotonic()


class ConfirmationSession:
    def __init__(self) -> None:
        self.pending_cmd_id: Optional[str] = None
        self.expires_at_monotonic: float = 0.0
        self.params: Dict[str, str] = {}


def builtin_rules_ordered() -> List[BuiltinMatchRule]:
    tbl: Iterable[BuiltinMatchRule] = (
        BuiltinMatchRule("CMD-02", 90, "wake", _anchor(_WAKE_P), 0),
        BuiltinMatchRule("CMD-01", 89, "sleep", _anchor(_SLEEP_P), 0),
        BuiltinMatchRule("CMD-14", 80, "click_through_on", _anchor(_CT_ON_P), 0),
        BuiltinMatchRule("CMD-15", 79, "click_through_off", _anchor(_CT_OFF_P), 0),
        BuiltinMatchRule("CMD-05", 70, "silent_mode_on", _anchor(_SILENT_ON_P), 0),
        BuiltinMatchRule("CMD-06", 70, "silent_mode_off", _anchor(_SILENT_OFF_P), 0),
        BuiltinMatchRule("CMD-03", 60, "observer_start", _anchor(obs_start_pat), 5),
        BuiltinMatchRule("CMD-04", 60, "observer_stop", _anchor(obs_stop), 0),
        BuiltinMatchRule("CMD-17", 55, "manual_game_set", _anchor(_GAME_MANUAL_P), 0),
        BuiltinMatchRule("CMD-18", 55, "manual_game_clear", _anchor(_GAME_AUTO_P), 0),
        BuiltinMatchRule("CMD-12", 50, "change_persona", _anchor(_PERSONA_P), 0),
        BuiltinMatchRule("CMD-11", 45, "set_interval", _anchor(_INTERVAL_P), 0),
        BuiltinMatchRule("CMD-07", 40, "backup", _anchor(_BACKUP_P), 300),
        BuiltinMatchRule("CMD-13", 40, "change_character", _anchor(_CHARACTER_P), 0),
        BuiltinMatchRule("CMD-16", 40, "forget_cache", _anchor(forget_p), 30),
        BuiltinMatchRule("CMD-08", 35, "session_report", _anchor(_SESSION_REP_P), 60),
        BuiltinMatchRule("CMD-10", 30, "reload_config", _anchor(_REL_CFG_P), 10),
        BuiltinMatchRule("CMD-09", 20, "open_documents", _anchor(_OPEN_DOC_P), 5),
        BuiltinMatchRule("CMD-19", 45, "check_league_hint", _anchor(_LEAGUE_HINT_P), 30),
        BuiltinMatchRule("CMD-20", 45, "daily_check", _anchor(_DAILY_CHECK_P), 120),
    )
    return sorted(tbl, key=lambda r: (-r.priority, r.cmd_id))


def split_command_segments(text: str) -> List[str]:
    nt = normalize(text)
    if not nt:
        return []
    return [normalize(p) for p in nt.split(" i ") if normalize(p)]


def _params_from_persona(m: re.Match[str]) -> Dict[str, str]:
    for key in ("name", "name_b", "name_c"):
        v = m.groupdict().get(key)
        if v:
            return {"name": v}
    return {}


def _params_from_character(m: re.Match[str]) -> Dict[str, str]:
    for key in ("char", "char2", "char3"):
        v = m.groupdict().get(key)
        if v:
            return {"char": str(v).strip()}
    return {}


def _try_builtin_on_norm(
    norm_text: str,
    rules: Sequence[BuiltinMatchRule],
) -> Optional[CommandMatch]:
    for rule in rules:
        m = rule.pattern.match(norm_text)
        if not m:
            continue
        params: Dict[str, str] = {}
        gd = m.groupdict()
        if "n" in gd and gd["n"] is not None:
            params["n"] = gd["n"]
        if any(k in gd for k in ("name", "name_b", "name_c")):
            params.update(_params_from_persona(m))
        if any(k in gd for k in ("char", "char2", "char3")):
            params.update(_params_from_character(m))
        if gd.get("game_id"):
            params["game_id"] = str(gd["game_id"]).strip().lower()
        return CommandMatch(
            cmd_id=rule.cmd_id,
            builtin_action=rule.builtin_action,
            params=params,
            confidence=1.0,
            cooldown_seconds=rule.cooldown_seconds,
            tool_name=None,
        )
    return None


def _fuzzy_fallback(norm_text: str, *, max_dist: int = 2) -> Optional[CommandMatch]:
    if norm_text.startswith("nie "):
        return None

    canon = "idz spac"
    d = levenshtein(norm_text, canon)
    if d > max_dist:
        return None
    conf = 1.0 - (d / max(len(norm_text), len(canon), 1))
    if conf < COMMAND_CONFIDENCE_THRESHOLD:
        return None
    return CommandMatch(
        cmd_id="CMD-01",
        builtin_action="sleep",
        params={},
        confidence=float(min(1.0, conf)),
        cooldown_seconds=0,
        tool_name=None,
    )


class CommandMatcher:
    def __init__(
        self,
        *,
        fuzzy: bool = True,
        builtins: Optional[Sequence[BuiltinMatchRule]] = None,
        custom: Optional[Sequence[CustomMatchRule]] = None,
    ) -> None:
        self._fuzzy = fuzzy
        self._builtins = list(builtins) if builtins else builtin_rules_ordered()
        self._custom = list(custom or [])

    def match_one(self, text: str, *, fuzzy: Optional[bool] = None) -> Optional[CommandMatch]:
        use_fuzzy = self._fuzzy if fuzzy is None else fuzzy
        nt = normalize(text)
        if not nt:
            return None
        m = self._match_custom(nt)
        if m:
            return m

        matched = _try_builtin_on_norm(nt, self._builtins)
        if matched:
            return matched

        if use_fuzzy:
            fm = _fuzzy_fallback(nt)
            if fm:
                return fm
        return None

    def match_all_segments(self, text: str, *, fuzzy: Optional[bool] = None) -> List[CommandMatch]:
        out: List[CommandMatch] = []
        for seg in split_command_segments(text):
            mm = CommandMatcher(fuzzy=self._fuzzy if fuzzy is None else fuzzy, builtins=self._builtins, custom=self._custom).match_one(seg, fuzzy=fuzzy)
            if mm:
                out.append(mm)
        if out:
            return out
        m = self.match_one(text, fuzzy=fuzzy)
        return [m] if m else []

    def _match_custom(self, norm_text: str) -> Optional[CommandMatch]:
        for rule in sorted(self._custom, key=lambda r: -r.priority):
            m = rule.pattern.match(norm_text)
            if not m:
                continue
            params = {k: v for k, v in m.groupdict().items() if v is not None}
            return CommandMatch(
                cmd_id=rule.cmd_id,
                builtin_action=None,
                params=params,
                confidence=1.0,
                cooldown_seconds=rule.cooldown_seconds,
                tool_name=rule.tool_name,
            )
        return None


__all__ = [
    "COMMAND_CONFIDENCE_THRESHOLD",
    "BuiltinMatchRule",
    "CooldownTracker",
    "CommandMatch",
    "CommandMatcher",
    "ConfirmationSession",
    "CustomMatchRule",
    "builtin_rules_ordered",
    "levenshtein",
    "normalize",
    "split_command_segments",
]
