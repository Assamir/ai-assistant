from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

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
    model_name: str = "moondream2"

class ObserverConfig(BaseModel):
    observer_type: str = "strategy"  # strategy or casual
    check_interval_seconds: int = 5
    skip_conditions: List[str] = Field(
        default_factory=lambda: ["game_paused", "low_fps"]
    )
    game_detection_method: str = "psutil"

class MCPConfig(BaseModel):
    enabled: bool = True
    tools_enabled: List[str] = Field(default_factory=list)
    cache_ttl_seconds: int = 3600

class ConfigSchema(BaseModel):
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