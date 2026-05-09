from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
from enum import Enum


class GeneralConfig(BaseModel):
    assistant_name: str = "Aria"
    content_root: str = "."


class AIControlConfig(BaseModel):
    max_context_tokens: int = Field(default=4096, ge=512, le=128_000)
    command_match_fuzzy: bool = True
    max_tool_calls_per_turn: int = Field(default=5, ge=1, le=50)
    mirror_tool_results_as_user: bool = Field(
        default=False,
        description=(
            "Po każdej wiadomości role=tool dodatkowa wiadomość user z tą samą treścią — obejście modeli lokalnych "
            "(np. część presetów Gemmy w LM Studio), które ignorują wyniki narzędzi w standardowym formacie."
        ),
    )

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

class CommandParamType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    CHOICE = "choice"

class CommandParam(BaseModel):
    name: str
    type: CommandParamType
    required: bool = True
    description: Optional[str] = None
    choices: Optional[List[str]] = None

class CommandSpec(BaseModel):
    name: str
    description: str
    params: List[CommandParam]
    aliases: List[str] = Field(default_factory=list)

class PersonaConfig(BaseModel):
    name: str
    description: str
    role: str
    personality: str
    examples: List[str]

class AudioConfig(BaseModel):
    input_device: Optional[str] = None
    output_device: Optional[str] = None
    sample_rate: int = 16000
    chunk_size: int = 1024
    input_mode: Literal["ptt", "wakeword"] = "ptt"
    backend_ptt_listener_enabled: bool = Field(
        default=False,
        description="Globalny hotkey PTT przez pynput w procesie backendu (Windows).",
    )
    ptt_key_name: str = Field(
        default="caps_lock",
        description="Nazwa klawisza dla pynput (np. caps_lock, f13, scroll_lock).",
    )
    wakeword_enabled: bool = False
    wakeword_models: List[str] = Field(
        default_factory=lambda: ["hey_jarvis"],
        description="Prebuilt openWakeWord — domyślnie hey_jarvis (fallback PRD).",
    )
    wakeword_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    strip_wake_phrase_from_transcription: bool = Field(
        default=True,
        description="Po STT usuń wiodącą frazę z wake_transcription_prefixes (np. „Hej Aria”) przed chat.",
    )
    wake_transcription_prefixes: List[str] = Field(
        default_factory=lambda: ["hej aria", "hej, aria", "cześć aria"],
        description="Frazy (PL) do obcięcia z początku transkryptu — uzupełnia openWakeWord (tylko modele EN).",
    )

    @field_validator("wake_transcription_prefixes", mode="before")
    @classmethod
    def normalize_wake_prefixes(cls, v: Any) -> List[str]:
        if v is None:
            return ["hej aria", "hej, aria", "cześć aria"]
        if isinstance(v, str):
            parts = [x.strip() for x in v.split(",") if x.strip()]
            return parts or ["hej aria", "hej, aria", "cześć aria"]
        out = [str(x).strip() for x in v if str(x).strip()]
        return out or ["hej aria", "hej, aria", "cześć aria"]

class LLMConfig(BaseModel):
    api_base_url: str = "http://localhost:1234"
    model_name: str = "gemma-2b-it-Q4_K_M"
    temperature: float = 0.7
    max_tokens: int = 512

class STTConfig(BaseModel):
    model_name: str = "large-v3"
    language: str = "pl"
    confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    confidence_floor: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description="Poniżej tej wartości wynik jest REJECT (powyżej + < threshold → LOW).",
    )
    beam_size: int = Field(default=5, ge=1, le=16)

class TTSConfig(BaseModel):
    model_name: str = "tts_models/pl_PL/mai_female"
    voice_speed: float = Field(default=1.0, ge=0.25, le=3.0)
    emotion_modulation: bool = True
    piper_executable: str = "piper"
    piper_voice_onnx_path: Optional[str] = None
    chunk_bytes: int = Field(default=4096, ge=512, le=65536)

class VLMConfig(BaseModel):
    """Vision-language (Moondream2 przez transformers); domyślnie wyłączone — brak torch w CI."""

    enabled: bool = False
    model_name: str = "vikhyatk/moondream2"
    revision: Optional[str] = Field(
        default="2025-06-21",
        description="Rewizja HF (vikhyatk/moondream2); None = domyślna gałąź.",
    )
    device: Literal["auto", "cuda", "cpu", "mps"] = "auto"
    dtype: Literal["auto", "float16", "float32", "bfloat16"] = "auto"
    caption_length: Literal["short", "normal"] = "normal"
    analysis_prompt: Optional[str] = Field(
        default=None,
        description="Jeśli ustawione — `model.query(image, prompt)` zamiast caption.",
    )
    gpu_priority: int = Field(default=4, ge=1, le=4, description="GPUScheduler: VLM = najniższy priorytet (4).")

    @field_validator("model_name", mode="before")
    @classmethod
    def normalize_legacy_model_name(cls, v: Any) -> str:
        if isinstance(v, str) and v.strip() == "moondream2":
            return "vikhyatk/moondream2"
        if v is None or (isinstance(v, str) and not str(v).strip()):
            return "vikhyatk/moondream2"
        return str(v).strip()

class OCRConfig(BaseModel):
    """EasyOCR — opcjonalny; domyślnie wyłączony (CI bez easyocr)."""

    enabled: bool = False
    languages: List[str] = Field(default_factory=lambda: ["pl", "en"])
    use_gpu: bool = True
    gpu_priority: int = Field(default=4, ge=1, le=4)
    confidence_threshold: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimalna pewność EasyOCR na linię (0 = bez filtrowania).",
    )
    trigger_keywords: List[str] = Field(
        default_factory=list,
        description=(
            "Puste → OCR zawsze po VLM (gdy VLM jest). Niepuste → OCR tylko gdy opis VLM "
            "zawiera którykolwiek substring (case-insensitive). Bez VLM — OCR zawsze."
        ),
    )

    @field_validator("languages", mode="before")
    @classmethod
    def normalize_langs(cls, v: Any) -> List[str]:
        if not v:
            return ["pl", "en"]
        if isinstance(v, str):
            return [v.strip()] if v.strip() else ["pl", "en"]
        return [str(x).strip() for x in v if str(x).strip()] or ["pl", "en"]

    @field_validator("trigger_keywords", mode="before")
    @classmethod
    def normalize_keywords(cls, v: Any) -> List[str]:
        if not v:
            return []
        return [str(x).strip().lower() for x in v if str(x).strip()]


class ObserverConfig(BaseModel):
    observer_type: str = "strategy"  # strategy or casual
    check_interval_seconds: int = Field(
        default=5,
        ge=1,
        le=600,
        description="Interwał `GameObserver` — odpytywanie psutil / wykrywanie procesu gry.",
    )
    cycle_interval_seconds: int = Field(
        default=20,
        ge=5,
        le=300,
        description="Interwał pętli capture→VLM→LLM gdy obserwator jest aktywny (T6).",
    )
    vlm_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        le=120.0,
        description="Timeout na `vision_pipeline.analyze_png` (backpressure / skip cyklu).",
    )
    scene_dhash_max_distance: int = Field(
        default=5,
        ge=0,
        le=32,
        description="SceneDeduper: max odległość Hamminga między klatkami uznawana za 'tę samą' scenę.",
    )
    observer_comment_max_tokens: int = Field(default=128, ge=16, le=1024)
    min_comment_interval_seconds: float = Field(
        default=25.0,
        ge=0.0,
        le=600.0,
        description="Po udanym komentarzu — pomiń kolejne cykle (bez capture/VLM) aż minie ten czas; 0 = wyłączone.",
    )
    comment_similarity_skip_threshold: float = Field(
        default=0.88,
        ge=0.0,
        le=1.0,
        description="Jeśli nowy tekst jest tak podobny do poprzedniego komentarza (SequenceMatcher), nie emituj go.",
    )
    persist_observer_comments: bool = Field(
        default=True,
        description="Zapis do SQLite (messages.source=observer) przy aktywnej sesji WS.",
    )
    skip_conditions: List[str] = Field(
        default_factory=lambda: ["game_paused", "low_fps"]
    )
    game_detection_method: str = "psutil"
    vlm_fallback_game_detection: bool = Field(
        default=False,
        description="Gdy brak dopasowania psutil/manual — periodycznie VLM+LLM dobiera profil po opisie ekranu (wymaga vlm.enabled).",
    )
    vlm_fallback_min_interval_seconds: int = Field(
        default=120,
        ge=30,
        le=3600,
        description="Minimalny odstęp między próbami fallbacku VLM (GameObserver).",
    )
    auto_league_hint_on_game_detected: bool = Field(
        default=False,
        description=(
            "Gdy True — po emisji `game_detected` (aktywna gra, znany `game_id` profilu) "
            "uruchom `check-league-hint`; przy rozbieżności broadcast WS `player_profile.league_hint`."
        ),
    )
    notification_sound_enabled: bool = Field(
        default=True,
        description="Czy odtwarzać krótki ping przed komentarzem obserwatora (F-VO-09).",
    )
    auto_session_report: bool = Field(
        default=False,
        description="Po zatrzymaniu gry automatycznie wyzwól podsumowanie sesji (CMD-08) dla aktywnych klientów WS.",
    )
    auto_session_report_min_turns: int = Field(
        default=3,
        ge=1,
        le=100,
        description="Minimalna liczba wiadomości w sesji, żeby uruchomić auto-raport.",
    )


class MonitorInfo(BaseModel):
    """Pojedynczy ekran / wyjście DXGI — `index` jest argumentem `capture_png(monitor_index=)`."""

    index: int = Field(ge=0, description="Liniowy indeks zgodny z kolejnością z list_monitors().")
    device_idx: int = Field(default=0, ge=0)
    output_idx: int = Field(default=0, ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    is_primary: bool = False
    label: str = ""

class MemoryConfig(BaseModel):
    """Pamięć semantyczna (Chroma / fallback) + katalog ``knowledge`` pod ``content_root``."""

    enabled: bool = Field(default=False, description="Gdy True — SemanticRecall + opcjonalny ingester przy starcie.")
    knowledge_dir: str = Field(
        default="knowledge",
        description="Podkatalog ``content_root`` z plikami .md/.txt do indeksowania.",
    )
    chroma_subdir: str = Field(
        default="chroma",
        description="Podkatalog ``data/`` dla Chroma PersistentClient (gdy ``chroma_persist``).",
    )
    chroma_persist: bool = Field(default=True, description="False = EphemeralClient (bez zapisu na dysk).")
    max_kb_chunks: int = Field(default=8_000, ge=100, le=500_000)
    chunk_size: int = Field(default=1200, ge=256, le=32_000)
    chunk_overlap: int = Field(default=200, ge=0, le=8_000)
    ingest_on_startup: bool = Field(default=True, description="Jednorazowy ingest ``knowledge_dir`` przy starcie.")
    watch_knowledge: bool = Field(
        default=False,
        description="Watchdog — ponowny ingest po zmianach plików (wątek w tle).",
    )
    inject_into_prompt: bool = Field(
        default=True,
        description="Wstrzykiwanie skrótów z KB do tur LLM (przed wiadomością użytkownika).",
    )
    recall_top_k: int = Field(default=4, ge=1, le=12)


class MCPConfig(BaseModel):
    enabled: bool = Field(
        default=True,
        description=(
            "Włącza narzędzie ``generate_document`` (zapis plików pod content_root). "
            "``web_search`` i ``web_scraper`` są zawsze rejestrowane dla LLM — dostępność sieciowa zależy od połączenia i limitów."
        ),
    )
    tools_enabled: List[str] = Field(default_factory=list)
    cache_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="TTL wpisów MCP cache dla narzędzi takich jak web_search.",
    )
    web_search_calls_per_minute: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Limit ścisły wywołań HTTP (web_search + web_scraper) na minutę — 11. zwraca błąd.",
    )
    use_playwright_fallback: bool = Field(
        default=False,
        description="Gdy httpx+ekstrakcja zwraca pusty tekst — próba renderu przez Playwright (wymaga playwright).",
    )
    daily_check_on_startup: bool = Field(
        default=False,
        description="Przy starcie backendu uruchom daily meta check dla każdej gry z profilu (w tle).",
    )
    daily_check_interval_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Minimalny odstęp między checkami dla tej samej gry (gdy force=false).",
    )
    scraper_allowed_hosts: List[str] = Field(
        default_factory=list,
        description=(
            "Opcjonalna lista dozwolonych hostów dla web_scraper (bez protokołu, np. maxroll.gg). "
            "Pusta lista = brak dodatkowego filtru (tylko http/https)."
        ),
    )


class ConfigSchema(BaseModel):
    general: GeneralConfig = GeneralConfig()
    ai_runtime: AIControlConfig = AIControlConfig()

    # Core config
    log_level: LogLevel = LogLevel.INFO
    
    # Audio settings
    audio: AudioConfig = AudioConfig()
    
    # LLM settings
    llm: LLMConfig = LLMConfig()
    
    # STT settings
    stt: STTConfig = STTConfig()
    
    # TTS settings
    tts: TTSConfig = TTSConfig()
    
    # VLM settings
    vlm: VLMConfig = VLMConfig()

    # OCR settings (EasyOCR)
    ocr: OCRConfig = OCRConfig()

    # Observer settings
    observer: ObserverConfig = ObserverConfig()
    
    # MCP settings
    mcp: MCPConfig = MCPConfig()

    # Semantic memory (T8)
    memory: MemoryConfig = MemoryConfig()
    
    # Quiet hours (cross-midnight support) — gdy `quiet_hours_enabled`, bez TTS w oknie czasu (tekst na overlay)
    quiet_hours_enabled: bool = Field(
        default=False,
        description="Gdy True — w godzinach quiet_hours_* wyłączany jest TTS (czat, obserwator, REST voice); komunikat na overlay.",
    )
    quiet_hours_start: str = "23:00"  # HH:MM format
    quiet_hours_end: str = "07:00"    # HH:MM format
    
    # Game profiles
    game_profiles: Dict[str, Any] = {}
    
    # Commands (from COMMANDS_SPEC)
    commands: List[CommandSpec] = Field(default_factory=list)

    # Personas
    personas: List[PersonaConfig] = Field(default_factory=list)