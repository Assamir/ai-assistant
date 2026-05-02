# DOK-07: COMMANDS_SPEC.md — Specyfikacja Komend Systemowych

> **Status:** v1.0 — 2026-04-30
> **Materiały źródłowe:** PRD_02_FUNCTIONAL.md (§9), PRD_05_UX_BEHAVIOR.md (User Stories), DECISIONS_LOG.md (DOK-07)
> **Zależności:** DOK-03 CONFIG_SPEC.md (klucz `ai.command_match_fuzzy`)

---

## Reguły naczelne

| # | Reguła | Materializacja |
|---|--------|---------------|
| 5 | Polski domyślny | Triggery PL są primary; EN opcjonalne |
| 7 | User interaction priority | Command matching odbywa się PRZED wysłaniem do LLM |
| 8 | Zero halucynacji | Komendy mają deterministyczne handlery — LLM nie jest pytany |

---

## 1. Wbudowane Komendy Systemowe

| ID | Komenda | Triggery PL | Triggery EN | Parametry | Handler | Confirmation | Cooldown |
|----|---------|-------------|-------------|-----------|---------|--------------|----------|
| CMD-01 | sleep | "idź spać", "śpij", "wyłącz się", "dobranoc", "uśnij" | "go to sleep", "sleep mode" | — | `SleepHandler` | none | 0s |
| CMD-02 | wake | "obudź się", "wróć", "hej wróć", "jesteś tu" | "wake up", "come back" | — | `WakeHandler` | none | 0s |
| CMD-03 | observer_start | "zacznij obserwować", "obserwuj", "włącz obserwatora", "patrz na grę", "śledź grę" | "start observing", "watch the game" | — | `ObserverStartHandler` | none | 5s |
| CMD-04 | observer_stop | "przestań obserwować", "stop obserwator", "wyłącz obserwatora", "nie obserwuj" | "stop observing", "stop watching" | — | `ObserverStopHandler` | none | 0s |
| CMD-05 | silent_mode_on | "wycisz się", "bądź cicho", "tryb cichy", "nie mów" | "be quiet", "silent mode" | — | `SilentModeOnHandler` | none | 0s |
| CMD-06 | silent_mode_off | "możesz mówić", "mów normalnie", "wróć do mówienia", "koniec ciszy" | "you can speak", "unmute" | — | `SilentModeOffHandler` | none | 0s |
| CMD-07 | backup | "zrób backup", "zrób kopię", "wykonaj backup", "kopia zapasowa" | "make backup", "create backup" | — | `BackupHandler` | none | 300s |
| CMD-08 | session_report | "podsumuj sesję", "podsumuj", "raport z sesji", "co robiłem" | "summarize session", "session report" | — | `SessionReportHandler` | none | 60s |
| CMD-09 | open_documents | "otwórz dokumenty", "pokaż dokumenty", "gdzie są dokumenty" | "open documents", "show documents" | — | `OpenDocumentsHandler` | none | 5s |
| CMD-10 | reload_config | "przeładuj konfigurację", "odśwież config", "załaduj ustawienia ponownie" | "reload config", "refresh config" | — | `ReloadConfigHandler` | none | 10s |
| CMD-11 | set_interval | "ustaw interwał na {n} sekund", "zmień interwał na {n}", "obserwuj co {n} sekund" | "set interval to {n} seconds" | `n: int (5–300)` | `SetIntervalHandler` | none | 0s |
| CMD-12 | change_persona | "zmień personę na {name}", "bądź {name}", "przełącz na personę {name}" | "switch to {name} persona", "be {name}" | `name: str` | `ChangePersonaHandler` | none | 0s |
| CMD-13 | change_character | "gram teraz {char}", "jestem teraz {char}", "zmień postać na {char}", "grę teraz {char}" | "playing as {char} now" | `char: str` | `ChangeCharacterHandler` | none | 0s |
| CMD-14 | click_through_on | "pozwól mi klikać", "idź na bok", "nie blokuj myszy" | "click through on", "let me click" | — | `ClickThroughOnHandler` | none | 0s |
| CMD-15 | click_through_off | "wróć na wierzch", "blokuj kliknięcia", "znowu aktywny" | "click through off", "block clicks" | — | `ClickThroughOffHandler` | none | 0s |
| CMD-16 | forget_cache | "odśwież informacje", "zapomnij cache", "wyczyść cache" | "refresh info", "clear cache" | — | `ForgetCacheHandler` | none | 30s |

**Uwaga:** Backup (CMD-07) nie wymaga potwierdzenia — jest non-destructive (tworzy ZIP, nic nie usuwa). Decyzja: DECISIONS_LOG DOK-07 #2.

---

## 2. Format `commands.yaml`

### 2.1 Pełna schema z walidacją Pydantic

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional, Union

class CommandTrigger(BaseModel):
    pattern: str          # Python regex z named groups: (?P<param_name>...)
    language: Literal["pl", "en", "both"] = "pl"

class CommandParam(BaseModel):
    type: Literal["string", "int", "float", "choice"] = "string"
    choices: Optional[list[str]] = None          # dla type=choice
    choices_dynamic: Optional[str] = None        # "${personas_available}" — runtime eval
    min: Optional[float] = None                  # dla int/float
    max: Optional[float] = None

class CustomCommand(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    triggers: list[CommandTrigger] = Field(min_length=1)
    params: dict[str, CommandParam] = {}
    action_type: Literal["builtin", "mcp_tool_call", "sequence"] = "builtin"
    action: str                                   # handler name lub tool name
    action_params: dict = {}                      # template z {param_name}
    priority: int = Field(default=50, ge=0, le=100)
    confirmation: Literal["none", "verbal", "auto"] = "none"
    cooldown_seconds: int = Field(default=0, ge=0)
    language: Literal["pl", "en", "both"] = "pl"

class CommandsConfig(BaseModel):
    version: int = 1
    commands: list[CustomCommand] = []
```

### 2.2 Przykładowy `commands.yaml`

```yaml
version: 1
commands:
  # Przykład 1: zmiana persony (builtin)
  - id: change_persona
    triggers:
      - pattern: "zmień personę na (?P<name>[\\w]+)"
        language: pl
      - pattern: "bądź (?P<name>[\\w]+)"
        language: pl
      - pattern: "switch to (?P<name>[\\w]+) persona"
        language: en
    params:
      name:
        type: choice
        choices_dynamic: "${personas_available}"
    action_type: builtin
    action: change_persona
    priority: 50
    confirmation: none
    cooldown_seconds: 0

  # Przykład 2: sprawdzenie pogody (mcp_tool_call)
  - id: check_weather
    triggers:
      - pattern: "jaka jest pogoda w (?P<city>[\\w\\s]+)"
        language: pl
      - pattern: "sprawdź pogodę w (?P<city>[\\w\\s]+)"
        language: pl
    params:
      city:
        type: string
    action_type: mcp_tool_call
    action: web_search
    action_params:
      query: "pogoda {city} dziś"
    priority: 30
    confirmation: none
    cooldown_seconds: 30

  # Przykład 3: sekwencja (obserwuj + zmień personę)
  - id: gaming_mode
    triggers:
      - pattern: "tryb gamingowy"
        language: pl
      - pattern: "gaming mode"
        language: en
    action_type: sequence
    action: ""
    action_params:
      steps:
        - action_type: builtin
          action: change_persona
          params: { name: "komentator" }
        - action_type: builtin
          action: observer_start
    priority: 60
    cooldown_seconds: 10

  # Przykład 4: z parametrem liczbowym
  - id: set_volume
    triggers:
      - pattern: "ustaw głośność na (?P<level>\\d+)"
        language: pl
    params:
      level:
        type: int
        min: 0
        max: 100
    action_type: builtin
    action: set_tts_volume
    priority: 40
```

---

## 3. Parser i Pipeline

```
STT transcription (raw)
        │
        ▼
1. NORMALIZE
   - lowercase
   - usuń diakrytyki: ą→a, ę→e, ś→s, ź→z, ż→z, ó→o, ć→c, ń→n, ł→l
   - trim whitespace
   - usuń interpunkcję (! ? , .)
        │
        ▼
2. MATCH BUILT-IN (priorytety 0–100, wyższy = sprawdzany wcześniej)
   - Regex match z named groups
   - Fuzzy fallback jeśli config.ai.command_match_fuzzy = true (Levenshtein ≤ 2)
        │
        ├── MATCH → validate params → check cooldown → execute handler → DONE
        │
        ▼ (brak matchu wbudowanego)
3. MATCH CUSTOM (commands.yaml, posortowane wg priority DESC)
        │
        ├── MATCH → execute (builtin/mcp_tool_call/sequence) → DONE
        │
        ▼ (brak matchu)
4. FORWARD TO LLM
   → normalny przepływ orkiestratora
```

---

## 4. Algorytm Matchingu

### 4.1 Exact regex match

```python
import re
import unicodedata

def normalize(text: str) -> str:
    text = text.lower().strip()
    # usuń diakrytyki
    nfkd = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in nfkd if not unicodedata.combining(c))
    # usuń interpunkcję
    text = re.sub(r"[^\w\s]", "", text)
    return text

def try_exact_match(text: str, commands: list[Command]) -> Optional[CommandMatch]:
    norm = normalize(text)
    for cmd in sorted(commands, key=lambda c: -c.priority):
        for trigger in cmd.triggers:
            pattern = normalize(trigger.pattern)  # normalizuj wzorzec też
            m = re.fullmatch(pattern, norm)
            if m:
                return CommandMatch(command=cmd, params=m.groupdict(), confidence=1.0)
    return None
```

### 4.2 Fuzzy matching (Levenshtein ≤ 2)

Aktywny gdy `config.ai.command_match_fuzzy = True` (domyślnie TRUE — decyzja DECISIONS_LOG DOK-07 #1).

```python
from rapidfuzz import fuzz, process

def try_fuzzy_match(text: str, commands: list[Command]) -> Optional[CommandMatch]:
    norm = normalize(text)
    candidates = []
    for cmd in commands:
        for trigger in cmd.triggers:
            # Dla triggerów bez parametrów — pełne porównanie
            if "{" not in trigger.pattern:
                trigger_norm = normalize(trigger.pattern)
                score = fuzz.ratio(norm, trigger_norm)
                if score >= 85:  # ~Levenshtein ≤ 2 dla krótkich fraz
                    candidates.append((cmd, trigger, score, {}))
            else:
                # Dla triggerów z parametrami — partial match
                base = re.sub(r"\(\?P<[^>]+>[^)]+\)", "PARAM", trigger.pattern)
                base_norm = normalize(base).replace("param", "")
                if base_norm[:10] in norm:  # heurystyka prefix match
                    candidates.append((cmd, trigger, 80, {}))

    if not candidates:
        return None
    best = max(candidates, key=lambda x: x[2])
    return CommandMatch(command=best[0], params=best[3], confidence=best[2] / 100)
```

### 4.3 Confidence threshold

```python
COMMAND_CONFIDENCE_THRESHOLD = 0.75  # minimum dla execution
```

Poniżej progu → forward to LLM.

---

## 5. Handler Interface

```python
from typing import Protocol
from dataclasses import dataclass

@dataclass
class CommandResult:
    success: bool
    message: Optional[str] = None        # do TTS (None = handler zarządza sam)
    emotion: Optional[str] = None        # emocja po wykonaniu
    side_effects: list[str] = field(default_factory=list)  # log

class CommandHandler(Protocol):
    async def execute(self, params: dict, context: "OrchestratorContext") -> CommandResult: ...
    async def can_execute(self, context: "OrchestratorContext") -> tuple[bool, Optional[str]]: ...
```

### 5.1 Implementacje handlerów

| Handler | Co robi | Zależności |
|---------|---------|------------|
| `SleepHandler` | Ukrywa awatar (WS event `avatar:hide`), zatrzymuje observer, TTS "Dobranoc" | `ObserverService`, `WebSocketManager` |
| `WakeHandler` | Przywraca awatar, TTS "O, wróciłeś!" | `WebSocketManager` |
| `ObserverStartHandler` | Startuje `ObserverLoop`, zapisuje w `system_state` | `ObserverService`, `GameDetector` |
| `ObserverStopHandler` | Zatrzymuje `ObserverLoop` | `ObserverService` |
| `SilentModeOnHandler` | Ustawia `system_state.silent_mode = true`, WS event | `SystemStateService` |
| `SilentModeOffHandler` | Ustawia `system_state.silent_mode = false` | `SystemStateService` |
| `BackupHandler` | `zipfile.ZipFile` na content root → `backups/` | `BackupService`, filesystem |
| `SessionReportHandler` | LLM call z historią sesji → `generate_document` | `LLMClient`, `MessageRepository` |
| `OpenDocumentsHandler` | `os.startfile(documents_path)` | os |
| `ReloadConfigHandler` | `ConfigLoader.reload()` | `ConfigLoader` |
| `SetIntervalHandler` | `config.observer.default_interval_seconds = n` → hot-reload | `ConfigLoader` |
| `ChangePersonaHandler` | `PromptBuilder.set_persona(name)` | `PersonaLoader`, `PromptBuilder` |
| `ChangeCharacterHandler` | `PlayerProfileRepository.set_active_character(char)` | `PlayerProfileRepository` |
| `ClickThroughOnHandler` | WS IPC `window:click_through_on` → Electron `setIgnoreMouseEvents(true)` | `WebSocketManager` |
| `ClickThroughOffHandler` | WS IPC `window:click_through_off` | `WebSocketManager` |
| `ForgetCacheHandler` | `MCPCacheRepository.invalidate_all()` | `MCPCacheRepository` |

---

## 6. Priorytetyzacja

Gdy ≥2 komendy pasują do tego samego utterance:
1. **Wyższy `priority` wygrywa** (100 = najwyższy, 0 = najniższy)
2. Przy równym priority → pierwsza w liście (built-in przed custom)
3. Precyzyjniejszy match (wyższe confidence) wygrywa przy tym samym priority

Priorytety wbudowane:

| Komenda | Priority | Uzasadnienie |
|---------|----------|-------------|
| sleep/wake | 90 | Krytyczne stany systemu |
| click_through | 80 | Safety — użytkownik może nie móc kliknąć inaczej |
| silent_mode | 70 | Audio UX krytyczne |
| observer_start/stop | 60 | Aktywne zarządzanie |
| change_persona | 50 | Interakcja z AI |
| set_interval | 45 | Config |
| backup | 40 | Utility |
| change_character | 40 | Profil |
| session_report | 35 | Utility |
| reload_config | 30 | Config |
| open_documents | 20 | Utility |

---

## 7. Lokalizacja

| Komenda | PL | EN | Oba |
|---------|----|----|-----|
| sleep | ✅ | ✅ | ✅ |
| wake | ✅ | ✅ | ✅ |
| observer_start | ✅ | ✅ | ✅ |
| observer_stop | ✅ | ✅ | ✅ |
| silent_mode | ✅ | ✅ | ✅ |
| backup | ✅ | ✅ | ✅ |
| session_report | ✅ | ✅ | ✅ |
| set_interval | ✅ | ✅ | ✅ |
| change_persona | ✅ | ✅ | ✅ |
| change_character | ✅ | ✅ | ✅ |
| click_through | ✅ | ✅ | ✅ |
| open_documents | ✅ tylko | — | — |
| reload_config | ✅ tylko | — | — |

---

## 8. Confirmation Patterns

Żadna komenda wbudowana nie wymaga potwierdzenia w MVP (backup jest non-destructive). Mechanizm confirmation dla custom komend:

```python
class ConfirmationSession:
    pending_command: CustomCommand
    params: dict
    expires_at: float  # Unix timestamp, TTL=30s

# Flow verbal confirmation:
# 1. Komenda z confirmation="verbal" dopasowana
# 2. TTS: "Czy na pewno chcesz {action_description}? Powiedz 'tak' żeby potwierdzić."
# 3. Asystent: emocja `confused`, słucha 30s
# 4. "tak" / "tak, zrób to" → execute; "nie" lub timeout → cancel, TTS "Anuluję."
```

---

## 9. Cooldowns i Rate Limits

```python
class CooldownTracker:
    _last_executed: dict[str, float] = {}  # cmd_id → timestamp

    def can_execute(self, cmd_id: str, cooldown_seconds: int) -> bool:
        last = self._last_executed.get(cmd_id, 0.0)
        return (time.time() - last) >= cooldown_seconds

    def mark_executed(self, cmd_id: str) -> None:
        self._last_executed[cmd_id] = time.time()
```

Na cooldown: TTS "Jeszcze chwila, mogę to zrobić za N sekund."

---

## 10. Edge Cases

| Przypadek | Zachowanie |
|-----------|------------|
| Komenda w środku dłuższej wypowiedzi ("tak, dobra, idź spać teraz proszę") | **TAK wykrywaj** — parser sprawdza czy wzorzec zawiera się w utterance (nie tylko `fullmatch`, też `search`) z wyższym confidence cutoff (0.85) |
| Negacja ("nie idź spać") | **NIE wykonuj** — regex prefixed z `(?!nie\s)` dla triggerów które mogą być negowane |
| Kontekst: po pytaniu systemu odpowiedź "tak" | Confirmation session aktywna → "tak" = execute pending |
| Multi-command ("zacznij obserwować i zmień personę na komentator") | Rozdziel po "i" / "oraz" / "," → przetwarzaj sekwencyjnie, max 2 komendy w jednym utterance |
| Komenda poza kontekstem ("zacznij obserwować" gdy nie ma gry) | Handler zwraca error + TTS "Nie wykryłem żadnej gry. Odpal grę i spróbuj ponownie." |
| Nieznana persona ("zmień personę na xyzzy") | Handler: sprawdź dostępne → TTS "Nie ma persony o nazwie xyzzy. Dostępne: default, komentator." |

---

## 11. Custom Commands DSL — Przykłady

```yaml
# Przykład 1: string param — fetch URL
- id: read_url
  triggers:
    - pattern: "przeczytaj (?P<url>https?://\\S+)"
      language: pl
  params:
    url: { type: string }
  action_type: mcp_tool_call
  action: web_scraper
  action_params: { url: "{url}" }
  priority: 35

# Przykład 2: choice param — ustawianie trybu proaktywności
- id: set_proactivity
  triggers:
    - pattern: "bądź (?P<level>pasywny|umiarkowany|aktywny)"
      language: pl
  params:
    level:
      type: choice
      choices: ["pasywny", "umiarkowany", "aktywny"]
  action_type: builtin
  action: set_proactivity
  priority: 45

# Przykład 3: optional param
- id: web_search_custom
  triggers:
    - pattern: "szukaj (?P<query>.+)"
      language: pl
  params:
    query: { type: string }
  action_type: mcp_tool_call
  action: web_search
  action_params: { query: "{query}", max_results: 5 }
  priority: 25
```

---

## 12. Rejestracja Handlera

```python
# backend/core/commands/registry.py
from typing import Type

_HANDLER_REGISTRY: dict[str, Type[CommandHandler]] = {}

def register_handler(action_name: str):
    def decorator(cls: Type[CommandHandler]) -> Type[CommandHandler]:
        _HANDLER_REGISTRY[action_name] = cls
        return cls
    return decorator

# Użycie:
@register_handler("observer_start")
class ObserverStartHandler:
    async def execute(self, params: dict, context: OrchestratorContext) -> CommandResult:
        await context.observer_service.start()
        return CommandResult(success=True, message="Zaczynam obserwować.", emotion="excited")
```

Custom handlery (`action_type: builtin` z custom action name) muszą być zarejestrowane w `backend/core/commands/custom_handlers.py` — plik importowany przy starcie.

---

## 13. Przypadki Testowe

| ID | Input | Expected Match | Params |
|----|-------|----------------|--------|
| CMD-T-01 | "idź spać" | CMD-01 sleep | {} |
| CMD-T-02 | "id spac" | CMD-01 sleep (fuzzy) | {} |
| CMD-T-03 | "śpij teraz proszę" | CMD-01 sleep | {} |
| CMD-T-04 | "nie idź spać" | brak (negacja) | — |
| CMD-T-05 | "ustaw interwał na 15 sekund" | CMD-11 | {n: 15} |
| CMD-T-06 | "ustaw interval na 15 sekund" | CMD-11 (fuzzy) | {n: 15} |
| CMD-T-07 | "zmień personę na komentator" | CMD-12 | {name: "komentator"} |
| CMD-T-08 | "gram teraz TankMasterem" | CMD-13 | {char: "TankMasterem"} |
| CMD-T-09 | "czy jest pora na spanie?" | brak (question) → LLM | — |
| CMD-T-10 | "zacznij obserwowac i zmien persone na komentator" | CMD-03 + CMD-12 seq | — |
| CMD-T-11 | "zrob backup" | CMD-07 (fuzzy: brak diakrytyków) | {} |
| CMD-T-12 | "otwórz dokumenty" | CMD-09 | {} |
| CMD-T-13 | "sprawdź pogodę w Krakowie" | custom check_weather | {city: "Krakowie"} |
| CMD-T-14 | "co to jest?" | brak → LLM | — |
| CMD-T-15 | "można mówić" | CMD-06 (fuzzy: "można" ≈ "możesz") | {} |

---

*Dokument: DOK-07 COMMANDS_SPEC.md v1.0 — 2026-04-30*
*Następny: DOK-08 ALGORITHMS_SPEC.md*
