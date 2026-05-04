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

class ObserverConfig(BaseModel):
    observer_type: str = "strategy"  # strategy or casual
    check_interval_seconds: int = 5
    skip_conditions: List[str] = Field(
        default_factory=lambda: ["game_paused", "low_fps"]
    )
    game_detection_method: str = "psutil"


class MonitorInfo(BaseModel):
    """Pojedynczy ekran / wyjście DXGI — `index` jest argumentem `capture_png(monitor_index=)`."""

    index: int = Field(ge=0, description="Liniowy indeks zgodny z kolejnością z list_monitors().")
    device_idx: int = Field(default=0, ge=0)
    output_idx: int = Field(default=0, ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    is_primary: bool = False
    label: str = ""

class MCPConfig(BaseModel):
    enabled: bool = True
    tools_enabled: List[str] = Field(default_factory=list)
    cache_ttl_seconds: int = 3600

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
    
    # Observer settings
    observer: ObserverConfig = ObserverConfig()
    
    # MCP settings
    mcp: MCPConfig = MCPConfig()
    
    # Quiet hours (cross-midnight support)
    quiet_hours_start: str = "23:00"  # HH:MM format
    quiet_hours_end: str = "07:00"    # HH:MM format
    
    # Game profiles
    game_profiles: Dict[str, Any] = {}
    
    # Commands (from COMMANDS_SPEC)
    commands: List[CommandSpec] = Field(default_factory=list)

    # Personas
    personas: List[PersonaConfig] = Field(default_factory=list)