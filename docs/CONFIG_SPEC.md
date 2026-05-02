# CONFIG_SPEC.md — Specyfikacja Konfiguracji

> **Status:** v1.0
> **Data:** 2026-04-30
> **Źródło decyzji:** DECISIONS_LOG.md (v1.1) — nie podważaj wartości stąd.
> **Reguły naczelne:** env > config, błędy config → głos + log, quiet_hours globalne.

---

## Spis treści

1. [Loader — kolejność i hierarchia](#1-loader--kolejność-i-hierarchia)
2. [config.yaml — główna konfiguracja](#2-configyaml--główna-konfiguracja)
3. [commands.yaml — custom komendy](#3-commandsyaml--custom-komendy)
4. [game_profiles/\*.yaml — profile gier](#4-game_profilesyaml--profile-gier)
5. [personas/\*.md — pliki person](#5-personasmd--pliki-person)
6. [data/player_profile.yaml — profil gracza](#6-dataplayer_profileyaml--profil-gracza)
7. [Hot-reload — tabela per klucz](#7-hot-reload--tabela-per-klucz)
8. [Mapowanie klucz → komponent](#8-mapowanie-klucz--komponent)
9. [Zmienne środowiskowe (env override)](#9-zmienne-środowiskowe-env-override)
10. [Migracje wersji](#10-migracje-wersji)

---

## 1. Loader — kolejność i hierarchia

### 1.1 Hierarchia źródeł (DECISIONS_LOG DOK-03 #1)

```
defaults (hardcoded w Pydantic)
    ↓  nadpisane przez
config.yaml (c:\ai\asystent\config\config.yaml)
    ↓  nadpisane przez
zmienne środowiskowe (ASSYSTENT_*)
    ↓
wynik: effective config (używany przez aplikację)
```

**Zasada:** `env > config > defaults`. Env vars zawsze wygrywają.

### 1.2 Procedura ładowania (startup)

```python
# backend/config/loader.py

def load_config() -> AppConfig:
    # 1. Załaduj wartości domyślne (z Pydantic Field defaults)
    config = AppConfig()

    # 2. Wczytaj config.yaml (jeśli istnieje)
    config_path = Path(r"c:\ai\asystent\config\config.yaml")
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        config = AppConfig.model_validate(raw)   # Pydantic V2

    # 3. Nadpisz zmiennymi środowiskowymi (pydantic-settings auto)
    config = AppConfig(_env_file=None)  # env vars wczytane automatycznie

    # 4. Walidacja semantyczna (cross-field)
    _validate_semantic(config)

    # 5. Zapisz znormalizowaną wersję (z defaultami uzupełnionymi)
    _write_normalized(config, config_path)

    return config
```

### 1.3 Obsługa błędów konfiguracji (DECISIONS_LOG DOK-03 #2)

Gdy `config.yaml` jest nieparseowalny lub klucz ma błędną wartość:

```python
# Strategia: load defaults + log + powiadom głosem
try:
    config = AppConfig.model_validate(raw)
except ValidationError as e:
    logger.error(f"Config validation failed: {e}")
    config = AppConfig()  # fallback do defaults
    # Kolejka komunikatu głosowego przy starcie TTS:
    startup_voice_queue.append(
        "Wykryłem błąd w konfiguracji. Używam wartości domyślnych. "
        "Sprawdź plik config.yaml.",
        emotion="confused"
    )
```

Aplikacja **nie zatrzymuje się** — kontynuuje z defaultami i informuje użytkownika.

### 1.4 Zapis znormalizowanej konfiguracji

Po starcie backend zapisuje `config.yaml` z uzupełnionymi defaultami — user widzi pełny plik przy pierwszym starcie.

---

## 2. config.yaml — główna konfiguracja

### 2.1 Pydantic V2 Schema

```python
# backend/config/schema.py
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal, Annotated
import re

class GeneralConfig(BaseModel):
    language: Literal["pl", "en"] = "pl"
    proactivity_level: Literal["passive", "moderate", "active"] = "moderate"
    quiet_hours: list[str] = Field(default=["23:00", "07:00"], min_length=2, max_length=2)
    content_root: str = r"c:\ai\asystent"
    assistant_name: Literal["Aria", "Mira", "Zara", "Nova", "Stella", "Eve"] = "Aria"
    wakeword_phrase: str = "Hej {assistant_name}"  # wypełniany automatycznie

    @field_validator("quiet_hours")
    @classmethod
    def validate_quiet_hours(cls, v: list[str]) -> list[str]:
        pattern = re.compile(r"^\d{2}:\d{2}$")
        for t in v:
            if not pattern.match(t):
                raise ValueError(f"quiet_hours format musi być HH:MM, got: {t}")
        return v

    @model_validator(mode="after")
    def fill_wakeword(self) -> "GeneralConfig":
        self.wakeword_phrase = f"Hej {self.assistant_name}"
        return self


class AudioConfig(BaseModel):
    input_device: str = "default"
    output_device: str = "default"
    tts_volume: float = Field(default=0.8, ge=0.0, le=1.0)
    stt_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    stt_low_confidence_threshold: float = Field(default=0.4, ge=0.0, le=1.0)
    notification_sound: bool = True

    @model_validator(mode="after")
    def check_thresholds(self) -> "AudioConfig":
        if self.stt_low_confidence_threshold >= self.stt_confidence_threshold:
            raise ValueError(
                "stt_low_confidence_threshold musi być < stt_confidence_threshold"
            )
        return self


class ObserverConfig(BaseModel):
    default_interval_seconds: int = Field(default=10, ge=5, le=300)
    ambient_enabled: bool = False
    log_observer_comments: bool = True
    monitor_index: int | None = Field(default=None, ge=0, le=7)
    capture_backend: Literal["dxcam", "pyautogui"] = "dxcam"


class AIConfig(BaseModel):
    lm_studio_url: str = "http://127.0.0.1:1234/v1"
    default_model: str = "gemma-4-e4b"
    max_tool_calls_per_turn: int = Field(default=5, ge=1, le=10)
    streaming: bool = True
    command_match_fuzzy: bool = True   # Levenshtein ≤ 2 (DECISIONS_LOG DOK-07 #1)


class ModelsConfig(BaseModel):
    stt: Literal["faster-whisper-medium", "faster-whisper-small", "faster-whisper-large-v3"] = "faster-whisper-medium"
    tts: Literal["piper", "xttsv2"] = "piper"
    vlm: Literal["moondream2", "llava"] = "moondream2"
    models_path: str = r"c:\ai\asystent\models"
    piper_voice_path: str = r"c:\ai\asystent\models\piper\gosia\pl_PL-gosia-medium.onnx"
    whisper_compute_type: Literal["int8", "float16", "float32"] = "int8"
    vlm_enabled: bool = True


class StorageConfig(BaseModel):
    backend: Literal["sqlite", "postgres", "gcp_firestore"] = "sqlite"
    data_path: str = r"c:\ai\asystent\data"
    archive_days: int = Field(default=90, ge=7)
    semantic_memory_limit: int = Field(default=10000, ge=100)
    log_compression: Literal["7z", "zip", "none"] = "7z"


class DocumentsConfig(BaseModel):
    output_path: str = r"c:\ai\asystent\documents"
    default_format: Literal["md", "html"] = "md"
    auto_session_report: bool = False
    html_theme: Literal["dark", "light"] = "dark"
    html_diagrams: Literal["mermaid", "ascii", "none"] = "mermaid"


class McpConfig(BaseModel):
    web_search_rate_limit: int = Field(default=10, ge=1, le=60)
    cache_ttl_game_meta: int = Field(default=86400, ge=60)    # 24h
    cache_ttl_general: int = Field(default=3600, ge=60)       # 1h
    cache_ttl_scraper: int = Field(default=604800, ge=3600)   # 7 days
    daily_check_on_startup: bool = True
    use_playwright_fallback: bool = True   # DECISIONS_LOG DOK-10 #1
    web_search_backend: Literal["duckduckgo", "searxng"] = "duckduckgo"  # DOK-10 #2


class DebugConfig(BaseModel):
    enabled: bool = False
    save_screenshots: bool = False
    log_pipeline: bool = False
    overlay_status: bool = False


class PersonaConfig(BaseModel):
    active: str = "default"  # nazwa pliku (bez .md) w personas/


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ASSYSTENT_",
        env_nested_delimiter="__",
        env_file=None,
        extra="ignore",
    )

    config_version: int = 1
    general: GeneralConfig = GeneralConfig()
    audio: AudioConfig = AudioConfig()
    observer: ObserverConfig = ObserverConfig()
    ai: AIConfig = AIConfig()
    models: ModelsConfig = ModelsConfig()
    storage: StorageConfig = StorageConfig()
    documents: DocumentsConfig = DocumentsConfig()
    mcp: McpConfig = McpConfig()
    debug: DebugConfig = DebugConfig()
    persona: PersonaConfig = PersonaConfig()
```

### 2.2 Przykład minimalny (config.yaml)

Wystarczy nadpisać tylko to co się różni od defaultów:

```yaml
config_version: 1

general:
  assistant_name: "Eve"
  language: pl

audio:
  tts_volume: 0.9

ai:
  lm_studio_url: "http://127.0.0.1:1234/v1"

persona:
  active: "default"
```

### 2.3 Przykład pełny (config.yaml)

```yaml
config_version: 1

general:
  language: pl
  proactivity_level: moderate       # passive | moderate | active
  quiet_hours: ["23:00", "07:00"]   # globalne (przez cały tydzień)
  content_root: "C:\\ai\\asystent"
  assistant_name: "Aria"            # Aria | Mira | Zara | Nova | Stella | Eve
  # wakeword_phrase: wypełniany automatycznie jako "Hej {assistant_name}"

audio:
  input_device: "default"           # lub "wasapi:1234" — z GET /audio/devices
  output_device: "default"
  tts_volume: 0.8                   # [0.0, 1.0]
  stt_confidence_threshold: 0.7     # >= stt_low_confidence_threshold
  stt_low_confidence_threshold: 0.4 # < stt_confidence_threshold
  notification_sound: true

observer:
  default_interval_seconds: 10      # [5, 300]
  ambient_enabled: false
  log_observer_comments: true
  monitor_index: null               # null = auto (pygetwindow), int = manual override
  capture_backend: "dxcam"          # dxcam | pyautogui (fallback gdy AV blokuje)

ai:
  lm_studio_url: "http://127.0.0.1:1234/v1"
  default_model: "gemma-4-e4b"
  max_tool_calls_per_turn: 5        # [1, 10]
  streaming: true
  command_match_fuzzy: true         # Levenshtein ≤ 2

models:
  stt: "faster-whisper-medium"      # faster-whisper-medium | small | large-v3
  tts: "piper"                      # piper | xttsv2
  vlm: "moondream2"                 # moondream2 | llava
  models_path: "C:\\ai\\asystent\\models"
  piper_voice_path: "C:\\ai\\asystent\\models\\piper\\gosia\\pl_PL-gosia-medium.onnx"
  whisper_compute_type: "int8"      # int8 | float16 | float32
  vlm_enabled: true

storage:
  backend: sqlite                   # sqlite | postgres | gcp_firestore
  data_path: "C:\\ai\\asystent\\data"
  archive_days: 90                  # >= 7
  semantic_memory_limit: 10000      # >= 100
  log_compression: "7z"             # 7z | zip | none

documents:
  output_path: "C:\\ai\\asystent\\documents"
  default_format: md                # md | html
  auto_session_report: false
  html_theme: dark                  # dark | light
  html_diagrams: mermaid            # mermaid | ascii | none

mcp:
  web_search_rate_limit: 10         # [1, 60] req/min
  cache_ttl_game_meta: 86400        # 24h [s]
  cache_ttl_general: 3600           # 1h [s]
  cache_ttl_scraper: 604800         # 7 days [s]
  daily_check_on_startup: true
  use_playwright_fallback: true
  web_search_backend: "duckduckgo"  # duckduckgo | searxng

debug:
  enabled: false
  save_screenshots: false
  log_pipeline: false
  overlay_status: false

persona:
  active: "default"                 # plik personas/default.md
```

### 2.4 Walidacja semantyczna (cross-field)

| Reguła | Sprawdzenie | Błąd |
|--------|-------------|------|
| `stt_low < stt_high` | `stt_low_confidence_threshold < stt_confidence_threshold` | `ValueError` → fallback defaults dla obu |
| `quiet_hours format` | `HH:MM` regex dla obu elementów | `ValueError` → brak quiet hours |
| `archive_days >= 7` | Minimalna retencja | `ValueError` → default 90 |
| `models_path istnieje` | `Path(models_path).exists()` | Ostrzeżenie log, nie crash |
| `persona.active` istnieje | `Path(personas/{active}.md).exists()` | Ostrzeżenie głosowe + fallback "default" |
| `piper_voice_path` istnieje | `.onnx` i `.onnx.json` | TTS disabled, ostrzeżenie głosowe |

> **Quiet hours semantyka:** `["23:00", "07:00"]` oznacza **nocną ciszę** — start może być późniejszy niż end (overflow przez północ). Implementacja sprawdza current_time ≥ start OR current_time < end.

---

## 3. commands.yaml — custom komendy

### 3.1 Lokalizacja i przeznaczenie

`c:\ai\asystent\config\commands.yaml` — komendy definiowane przez użytkownika,
przetwarzane **przed** LLM (bez kosztu tokenów). Hot-reload ✅.

### 3.2 Schema (Pydantic V2)

```python
from pydantic import BaseModel, Field
from typing import Literal

class CommandTrigger(BaseModel):
    pattern: str                        # regex z named groups {param}
    language: Literal["pl", "en"] = "pl"

class CommandParam(BaseModel):
    type: Literal["string", "int", "float"] = "string"
    required: bool = True

class CustomCommand(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]+$")  # snake_case, unikalne
    triggers: list[CommandTrigger] = Field(min_length=1)
    params: dict[str, CommandParam] = {}
    action_type: Literal["builtin", "mcp_tool_call", "sequence"] = "builtin"
    action: str                         # nazwa built-in lub tool MCP
    action_params: dict = {}
    priority: int = Field(default=50, ge=0, le=100)  # niższy = wyższy priorytet
    enabled: bool = True
```

### 3.3 Przykład pełny (commands.yaml)

```yaml
# c:\ai\asystent\config\commands.yaml
# Hot-reload: tak. Edytuj i zapisz — asystent poinformuje głosowo.

- id: set_observer_interval
  triggers:
    - pattern: "ustaw interwał na {interval} sekund"
      language: pl
    - pattern: "set interval to {interval} seconds"
      language: en
  params:
    interval:
      type: int
      required: true
  action_type: builtin
  action: set_observer_interval
  action_params:
    min: 5
    max: 300
  priority: 10

- id: change_persona
  triggers:
    - pattern: "zmień personę na {name}"
      language: pl
    - pattern: "bądź {name}"
      language: pl
  params:
    name:
      type: string
      required: true
  action_type: builtin
  action: change_persona
  priority: 10

- id: weather_check
  triggers:
    - pattern: "sprawdź pogodę w {city}"
      language: pl
  params:
    city:
      type: string
      required: true
  action_type: mcp_tool_call
  action: web_search
  action_params:
    query: "pogoda {city} dzisiaj"
  priority: 30
```

### 3.4 Wbudowane action_type: builtin — dostępne akcje

| Nazwa akcji | Opis | Parametry |
|-------------|------|-----------|
| `set_observer_interval` | Zmień interwał obserwatora | `interval: int` |
| `change_persona` | Załaduj inną personę | `name: str` |
| `toggle_silent` | Wycisz/odcisz TTS | — |
| `toggle_sleep` | Ukryj/pokaż awatar | — |
| `backup` | Zrób backup | — |
| `open_folder` | Otwórz folder w Explorer | `folder: str` |
| `summarize_session` | Generuj raport z sesji | — |
| `start_observer` | Uruchom pętlę obserwatora | — |
| `stop_observer` | Zatrzymaj pętlę obserwatora | — |
| `change_active_character` | Zmień aktywną postać | `character: str` |

### 3.5 Fuzzy matching (DECISIONS_LOG DOK-07 #1)

Domyślnie włączony (`ai.command_match_fuzzy: true`).
- Algorytm: Levenshtein distance ≤ 2 na triggerze po tokenizacji
- Przykład: "ustaw interfał na 15 sekund" → dopasuje "ustaw interwał na {interval} sekund"
- Wyłącz gdy precyzja ważniejsza niż tolerancja: `ai.command_match_fuzzy: false`

---

## 4. game_profiles/*.yaml — profile gier

### 4.1 Lokalizacja

`c:\ai\asystent\config\game_profiles\{game_id}.yaml`

Reguła nazwy pliku: `^[a-z0-9_]+\.yaml$`

Hot-reload ✅ — zmiana pliku powoduje przeładowanie profilu bez restartu.

### 4.2 Schema (Pydantic V2)

```python
class ScreenRegion(BaseModel):
    name: str
    position: Literal["top-left", "top-right", "bottom-left", "bottom-right", "center", "full"]
    size: str = Field(pattern=r"^\d+%$")  # procent ekranu, np. "15%"

class GameProfile(BaseModel):
    name: str                           # nazwa wyświetlana, np. "Path of Exile 2"
    process_names: list[str] = Field(min_length=1)  # nazwy .exe do detekcji
    observer_type: Literal["action", "strategy", "idle"] = "action"
    observer_interval_seconds: int = Field(default=10, ge=5, le=300)
    focus_areas: list[str] = []         # tematy analizy VLM (hints dla LLM)
    screen_regions: list[ScreenRegion] = []
    context_prompt: str = ""            # dodatkowy prompt dla tego profilu
    mcp_sources: list[str] = []         # preferowane źródła web_search
    ocr_enabled: bool = True            # DECISIONS_LOG DOK-09 #3: per-profile
    vlm_enabled: bool = True
```

### 4.3 Przykłady

**`config/game_profiles/poe2.yaml`:**
```yaml
name: "Path of Exile 2"
process_names:
  - "PathOfExile_x64.exe"
  - "PathOfExileSteam.exe"
observer_type: action
observer_interval_seconds: 5
focus_areas:
  - builds
  - loot
  - combat
  - boss_mechanics
screen_regions:
  - name: "health_mana"
    position: "bottom-left"
    size: "15%"
  - name: "minimap"
    position: "top-right"
    size: "15%"
context_prompt: |
  Jesteś ekspertem od Path of Exile 2. Skupiaj się na:
  - Analizie przedmiotów (affixy, tier, wartość dla buildu gracza)
  - Ostrzeganiu przed niebezpieczeństwami
  - Sugestiach dotyczących buildu i mechanik gry
mcp_sources:
  - "poe2 wiki"
  - "maxroll.gg/poe2"
ocr_enabled: true    # tooltopy itemów wymagają OCR
vlm_enabled: true
```

**`config/game_profiles/stellaris.yaml`:**
```yaml
name: "Stellaris"
process_names:
  - "stellaris.exe"
observer_type: strategy
observer_interval_seconds: 30       # wolniejszy cykl dla strategii
focus_areas:
  - empire_management
  - diplomacy
  - fleet_composition
  - research_priorities
screen_regions:
  - name: "full_screen"
    position: "full"
    size: "100%"
context_prompt: |
  Jesteś ekspertem od Stellaris. Analizuj mapę galaktyki, imperium gracza,
  sytuację dyplomatyczną i militarną. Proponuj strategie ekspansji i obrony.
mcp_sources:
  - "stellaris wiki"
  - "reddit.com/r/Stellaris"
ocr_enabled: false    # strategia — VLM wystarczy, brak item tooltipów
vlm_enabled: true
```

### 4.4 Walidacja

- `process_names` musi mieć ≥ 1 element
- `observer_interval_seconds ∈ [5, 300]`
- `size` w `screen_regions` musi być `\d+%`
- Plik wykryty przez game detector musi istnieć w katalogu `game_profiles/`

---

## 5. personas/*.md — pliki person

### 5.1 Lokalizacja

`c:\ai\asystent\personas\{name}.md`

Reguła nazwy: `^[a-z0-9_-]+\.md$`

Hot-reload ✅ — zmiana pliku (lub dodanie nowego) widoczna natychmiast po `POST /personas/reload` lub auto-detect przez watchdog.

### 5.2 Struktura: YAML frontmatter + body Markdown

```markdown
---
name: "default"                     # musi = nazwa pliku (bez .md)
version: "1.0"
language: pl
style:
  - sarkastyczny
  - pomocny
  - żartobliwy
  - bezpośredni
emotion_bias:                        # modyfikatory intensywności emocji [0.0–2.0]
  amused: 1.4                        # częściej i silniej rozbawiona
  sarcastic: 1.3
  thoughtful: 1.1
  excited: 0.8                       # rzadziej podekscytowana
---

# Persona: Default

Jesteś inteligentnym asystentem gracza o imieniu {assistant_name}. Twój styl jest:
- **Sarkastyczny, ale pomocny** — komentarz z przymrużeniem oka, ale zawsze z meritum
- **Bezpośredni** — bez zbędnych wstępów, od razu do rzeczy
- **Żartobliwy** — szczególnie przy błędach gracza, ale nigdy złośliwie

## Zasady odpowiedzi

1. Mów krótko gdy pytanie proste, rozwiń gdy temat wymaga
2. Używaj polskich nazw gier i postaci (oryginalne tytuły EN zachowaj w nawiasie)
3. Nigdy nie zmyślaj — powiedz "nie wiem" lub "poszukam" (reguła Zero Halucynacji)
4. Nie pytaj o rzeczy które masz w profilu gracza — używaj ich bezpośrednio

## Przykładowe odpowiedzi

**Przy błędzie buildu:**
> "Ten link pancerza na Deadeye... odważna decyzja. Odważna i błędna. Sugeruję Life Flask + Quartz."

**Przy prostym pytaniu:**
> "Tak, Lightning Arrow po ostatnim patchu wciąż meta. Buff do damage na single target."
```

### 5.3 Schema frontmatter (Pydantic V2)

```python
class PersonaFrontmatter(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9_-]+$")
    version: str = "1.0"
    language: Literal["pl", "en"] = "pl"
    style: list[str] = []
    emotion_bias: dict[str, float] = {}  # klucz: emotion name, wartość: [0.0, 2.0]

    @field_validator("emotion_bias")
    @classmethod
    def validate_emotions(cls, v: dict) -> dict:
        valid = {
            "neutral","happy","amused","excited","sad","worried","confused",
            "thoughtful","focused","sarcastic","disappointed","surprised",
            "angry","tired","bored","affectionate"
        }
        for k, val in v.items():
            if k not in valid:
                raise ValueError(f"Nieznana emocja: {k}")
            if not 0.0 <= val <= 2.0:
                raise ValueError(f"emotion_bias[{k}] musi być w [0.0, 2.0]")
        return v
```

### 5.4 Placeholder w body

W body persony dostępne placeholdery (wypełniane przez PromptBuilder):
- `{assistant_name}` — imię asystenta z config
- `{player_name}` — imię gracza (opcjonalne, jeśli znane)
- `{active_game}` — aktualnie wykryta gra

---

## 6. data/player_profile.yaml — profil gracza

### 6.1 Lokalizacja

`c:\ai\asystent\data\player_profile.yaml`

**Nie jest** w `config/` — to dane użytkownika, nie konfiguracja systemowa.
Hot-reload: **częściowy** — zmiana `active_character` hot-reload ✅; dodanie gry wymaga `POST /player-profile/reload`.

### 6.2 Schema (Pydantic V2)

```python
from datetime import date

class Character(BaseModel):
    name: str
    char_class: str = Field(alias="class")
    build: str = ""
    level: int = Field(default=1, ge=1, le=100)
    build_url: str | None = None
    notes: str = ""

class GameEntry(BaseModel):
    active_character: str | None = None
    league: str = ""          # dla gier z sezonami (PoE2)
    game_version: str = ""    # dla gier z patchami (Stellaris)
    characters: list[Character] = []
    last_meta_check: date | None = None

    @model_validator(mode="after")
    def check_active_character(self) -> "GameEntry":
        if self.active_character:
            names = [c.name for c in self.characters]
            if self.active_character not in names:
                raise ValueError(
                    f"active_character '{self.active_character}' nie istnieje w characters"
                )
        return self

class PlayerProfile(BaseModel):
    games: dict[str, GameEntry] = {}  # klucz = game_id (musi mieć profil w game_profiles/)
    updated_at: str = ""              # ISO 8601, auto-ustawiane przy zapisie
```

### 6.3 Przykład

```yaml
# c:\ai\asystent\data\player_profile.yaml
games:
  poe2:
    active_character: "SparkyBoy"
    league: "Season 2"
    characters:
      - name: "SparkyBoy"
        class: "Deadeye"
        build: "Lightning Arrow"
        level: 87
        build_url: "https://maxroll.gg/poe2/build-guides/lightning-arrow"
        notes: "Potrzebuje lepszego łuku — min. Tier 2 Lightning"
      - name: "TankMaster"
        class: "Marauder"
        build: "Slam Juggernaut"
        level: 42
        notes: "W trakcie levelowania"
    last_meta_check: "2026-04-28"
  stellaris:
    active_character: null
    game_version: "3.14"
    characters: []

updated_at: "2026-04-30T14:22:00Z"
```

---

## 7. Hot-reload — tabela per klucz

File watcher (`watchdog`) monitoruje: `config/`, `personas/`. Asystent głosowo informuje: "Zauważyłem zmianę konfiguracji, przeładowałem."

| Klucz / Plik | Hot-reload | Restart | Uwagi |
|---|---|---|---|
| `general.proactivity_level` | ✅ | | Natychmiastowy efekt |
| `general.quiet_hours` | ✅ | | Nowe godziny aktywne od razu |
| `general.language` | | 🔄 | Wpływa na system prompt, TTS, STT |
| `general.assistant_name` | | 🔄 | Wymaga swap modelu wakeword |
| `audio.tts_volume` | ✅ | | |
| `audio.stt_confidence_threshold` | ✅ | | |
| `audio.stt_low_confidence_threshold` | ✅ | | |
| `audio.notification_sound` | ✅ | | |
| `audio.input_device` | | 🔄 | Wymaga reinicjalizacji audio stream |
| `audio.output_device` | | 🔄 | |
| `observer.default_interval_seconds` | ✅ | | Efekt od następnego cyklu |
| `observer.ambient_enabled` | ✅ | | |
| `observer.log_observer_comments` | ✅ | | |
| `observer.monitor_index` | ✅ | | |
| `observer.capture_backend` | | 🔄 | Wymaga reinicjalizacji capture |
| `ai.max_tool_calls_per_turn` | ✅ | | |
| `ai.streaming` | ✅ | | |
| `ai.command_match_fuzzy` | ✅ | | |
| `ai.lm_studio_url` | | 🔄 | |
| `ai.default_model` | | 🔄 | Wymaga reload LM Studio |
| `models.stt` | | 🔄 | Wymaga reload modelu Whisper |
| `models.tts` | | 🔄 | Wymaga reload TTS engine |
| `models.vlm` | | 🔄 | Wymaga reload modelu VLM |
| `models.piper_voice_path` | | 🔄 | |
| `models.vlm_enabled` | ✅ | | |
| `models.whisper_compute_type` | | 🔄 | |
| `storage.archive_days` | ✅ | | |
| `storage.semantic_memory_limit` | ✅ | | |
| `storage.log_compression` | ✅ | | |
| `storage.backend` | | 🔄 | Wymaga migracji danych |
| `storage.data_path` | | 🔄 | |
| `documents.*` | ✅ | | Efekt dla następnego dokumentu |
| `mcp.web_search_rate_limit` | ✅ | | |
| `mcp.cache_ttl_*` | ✅ | | Nowe TTL dla nowych wpisów |
| `mcp.daily_check_on_startup` | ✅ | | |
| `mcp.use_playwright_fallback` | ✅ | | |
| `debug.*` | ✅ | | |
| `persona.active` | ✅ | | Hot-reload systemu promptów |
| `personas/*.md` | ✅ | | File watcher |
| `config/game_profiles/*.yaml` | ✅ | | File watcher |
| `config/commands.yaml` | ✅ | | File watcher |

---

## 8. Mapowanie klucz → komponent

| Klucz config | Komponent(y) |
|---|---|
| `general.language` | `PromptBuilder`, `STTEngine`, `TTSEngine` |
| `general.proactivity_level` | `Orchestrator`, `ObserverLoop` |
| `general.quiet_hours` | `Orchestrator` (gate przed wysłaniem observer events) |
| `general.content_root` | `SandboxValidator`, `BackupService`, `DocumentService` |
| `general.assistant_name` | `WakewordDetector`, `PromptBuilder` |
| `audio.input_device` | `AudioCapture` |
| `audio.output_device` | `AudioPlayback` |
| `audio.tts_volume` | `TTSEngine`, `AudioPlayback` |
| `audio.stt_confidence_threshold` | `STTEngine`, `Orchestrator` |
| `audio.stt_low_confidence_threshold` | `STTEngine` |
| `audio.notification_sound` | `AudioPlayback` |
| `observer.default_interval_seconds` | `ObserverLoop` |
| `observer.ambient_enabled` | `ObserverLoop` |
| `observer.log_observer_comments` | `SessionLogger` |
| `observer.monitor_index` | `ScreenCapture` |
| `observer.capture_backend` | `ScreenCapture` |
| `ai.lm_studio_url` | `LLMClient`, `HealthChecker` |
| `ai.default_model` | `LLMClient` |
| `ai.max_tool_calls_per_turn` | `Orchestrator`, `MCPToolRunner` |
| `ai.streaming` | `LLMClient`, `Orchestrator` |
| `ai.command_match_fuzzy` | `CommandMatcher` |
| `models.stt` | `STTEngine` |
| `models.tts` | `TTSEngine` |
| `models.vlm` | `VLMEngine` |
| `models.piper_voice_path` | `PiperTTSAdapter` |
| `models.vlm_enabled` | `ObserverLoop`, `ScreenCapture` |
| `storage.backend` | `StorageFactory` |
| `storage.data_path` | `SQLiteStorage`, `ChromaStorage` |
| `storage.archive_days` | `ArchiveScheduler` |
| `storage.semantic_memory_limit` | `SemanticMemory` |
| `storage.log_compression` | `SessionLogger` |
| `documents.output_path` | `DocumentService` |
| `documents.default_format` | `DocumentService` |
| `documents.auto_session_report` | `SessionManager` |
| `documents.html_theme` | `DocumentRenderer` |
| `documents.html_diagrams` | `DocumentRenderer` |
| `mcp.web_search_rate_limit` | `WebSearchTool` |
| `mcp.cache_ttl_*` | `MCPCache` |
| `mcp.daily_check_on_startup` | `DailyCheckScheduler` |
| `mcp.use_playwright_fallback` | `WebScraperTool` |
| `mcp.web_search_backend` | `WebSearchTool` |
| `debug.enabled` | `DebugRouter` (gate dla /debug/* endpointów) |
| `debug.save_screenshots` | `ScreenCapture` |
| `debug.log_pipeline` | `Orchestrator` |
| `debug.overlay_status` | `WebSocket` → Frontend |
| `persona.active` | `PromptBuilder`, `PersonaLoader` |

---

## 9. Zmienne środowiskowe (env override)

Format: `ASSYSTENT_{SEKCJA}__{KLUCZ}` (double underscore dla zagnieżdżenia, pydantic-settings).

| Zmienna środowiskowa | Klucz config | Przykład użycia |
|---|---|---|
| `ASSYSTENT_GENERAL__LANGUAGE` | `general.language` | `set ASSYSTENT_GENERAL__LANGUAGE=en` |
| `ASSYSTENT_GENERAL__ASSISTANT_NAME` | `general.assistant_name` | `set ASSYSTENT_GENERAL__ASSISTANT_NAME=Eve` |
| `ASSYSTENT_AI__LM_STUDIO_URL` | `ai.lm_studio_url` | `set ASSYSTENT_AI__LM_STUDIO_URL=http://127.0.0.1:1235/v1` |
| `ASSYSTENT_MODELS__PIPER_VOICE_PATH` | `models.piper_voice_path` | Override ścieżki głosu |
| `ASSYSTENT_STORAGE__DATA_PATH` | `storage.data_path` | `set ASSYSTENT_STORAGE__DATA_PATH=D:\asystent\data` |
| `ASSYSTENT_DEBUG__ENABLED` | `debug.enabled` | `set ASSYSTENT_DEBUG__ENABLED=true` |
| `ASSYSTENT_GENERAL__CONTENT_ROOT` | `general.content_root` | Override sandbox root |

Env vars **zawsze** nadpisują `config.yaml` — zasada `env > config` (DECISIONS_LOG DOK-03 #1).

---

## 10. Migracje wersji

### 10.1 Pole config_version

Każdy `config.yaml` musi mieć `config_version: int`. Brak pola → traktowane jako `version: 0`.

### 10.2 Skrypt migracji: `scripts/migrate_config.py`

```python
# Uruchomienie:
python scripts/migrate_config.py --config "C:\ai\asystent\config\config.yaml"

# Działanie:
# 1. Odczyt config_version z pliku
# 2. Zastosowanie migracji kolejno od current_version+1 do LATEST_VERSION
# 3. Zapis zaktualizowanego pliku (backup starego jako config.yaml.bak.{timestamp})

MIGRATIONS = {
    1: migrate_v0_to_v1,   # dodano: general.assistant_name, observer.monitor_index
    # 2: migrate_v1_to_v2  # przyszłe migracje
}
```

### 10.3 Tabela migracji

| From → To | Zmiany | Akcja automatyczna |
|---|---|---|
| 0 → 1 | Dodano `general.assistant_name`, `general.wakeword_phrase`, `observer.monitor_index`, `observer.capture_backend`, `ai.command_match_fuzzy`, `models.piper_voice_path`, `models.vlm_enabled`, `models.whisper_compute_type`, `mcp.use_playwright_fallback`, `mcp.web_search_backend` | Uzupełnij brakujące klucze defaultami |

### 10.4 Backward compatibility

Klucze **nieznane** (`extra="ignore"` w Pydantic) są ignorowane bez błędu — stare configy z nadmiarowymi kluczami nie crashują aplikacji.

---

## Reguły naczelne uwzględnione w tym dokumencie

| Reguła | Zastosowanie |
|--------|-------------|
| **env > config** | Hierarchia loader: defaults → config.yaml → env vars (sekcja 1.1) |
| **Komunikacja błędów głosem** | Błędny config → fallback + powiadomienie głosowe przy starcie TTS (sekcja 1.3) |
| **Offline-first** | Wszystkie ścieżki modeli lokalne; brak URL-i do chmury w defaults |
| **Sandbox twardy** | `content_root` jako punkt wyjścia dla wszystkich ścieżek danych; `SandboxValidator` używa tego klucza |
| **Modulárność** | Klucze `models.stt`, `models.tts`, `models.vlm` jako strategy pattern (mapowanie sekcja 8) |
| **Polski domyślny** | `general.language: pl`, `piper_voice_path` → gosia (PL żeński) jako default |
| **Awatar nigdy nie zamarza** | `debug.overlay_status` jako mechanizm feedback stanu podczas ładowania |
