# PRD 04: Architektura i Tech Stack

> Część 4/6 — [Powrót do indeksu](PRD_00_INDEX.md)

---

## 1. Architektura Wysokopoziomowa

```
┌────────────────────────────────────────────────────────────┐
│                  FRONTEND (Electron + React)                │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │  Awatar 3D   │  │  Panel UI / │  │  Audio Player    │  │
│  │  (Three.js + │  │  Konfigur.  │  │  + Lip-sync      │  │
│  │  three-vrm)  │  │  + Status   │  │  + Text Overlay  │  │
│  └──────┬───────┘  └──────┬──────┘  └────────┬─────────┘  │
│         └─────────────────┼──────────────────┘             │
│                     WebSocket / HTTP                        │
│              (heartbeat 5s, reconnect auto)                 │
└────────────────────────────┬───────────────────────────────┘
                             │
┌────────────────────────────┴───────────────────────────────┐
│                 BACKEND (Python 3.10+ / FastAPI)            │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              ORKIESTRATOR AI                         │   │
│  │  ┌────────────┐  ┌───────────┐  ┌────────────────┐  │   │
│  │  │  Prompt    │  │  Emotion  │  │  Command       │  │   │
│  │  │  Builder   │  │  Parser   │  │  Matcher       │  │   │
│  │  └────────────┘  └───────────┘  └────────────────┘  │   │
│  │  ┌────────────┐  ┌───────────┐  ┌────────────────┐  │   │
│  │  │  GPU       │  │  Circuit  │  │  Session       │  │   │
│  │  │  Scheduler │  │  Breaker  │  │  Watchdog      │  │   │
│  │  └────────────┘  └───────────┘  └────────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ Moduł    │ │ Moduł    │ │ Moduł    │ │ Moduł        │  │
│  │ STT      │ │ TTS      │ │ Wakeword │ │ VLM + OCR    │  │
│  │ (Faster- │ │ (Piper/  │ │ (open-   │ │ (Moondream2  │  │
│  │ Whisper) │ │ XTTSv2)  │ │ WakeWord)│ │ + EasyOCR)   │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ Screen   │ │ MCP      │ │ Memory   │ │ Document     │  │
│  │ Capture  │ │ Tools    │ │ Store    │ │ Generator    │  │
│  │ (DXcam)  │ │ (6 tools)│ │ (SQLite+ │ │ (MD/HTML)    │  │
│  │          │ │          │ │ ChromaDB)│ │              │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Input Handler (pynput) — PTT / Hotkeys               │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────┬───────────────────────────────┘
                             │ OpenAI-compatible API
┌────────────────────────────┴───────────────────────────────┐
│                  LM STUDIO (Serwer LLM)                     │
│                  Gemma 4 E4B                                │
│                  Function Calling enabled                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Tech Stack

| Warstwa | Technologia | Uzasadnienie |
|---------|-------------|-------------|
| **Frontend** | Electron.js + React.js | Natywne okno: transparentność, Always-on-Top, frameless |
| **Rendering 3D** | Three.js + three-vrm | Standard VRM, proceduralnie animowalne |
| **Backend** | Python 3.10+ / FastAPI | Async framework, ekosystem ML, auto-docs Swagger |
| **LLM** | Gemma 4 E4B (via LM Studio) | Lokalny, OpenAI API compatible, function calling |
| **STT** | Faster-Whisper (CTranslate2) | Szybka, dokładna transkrypcja PL/EN |
| **Wakeword** | openWakeWord | Lekki, konfigurowalny, CPU-only |
| **TTS** | Piper (domyślny) / XTTSv2 | Piper: ultraszybki, niski VRAM. XTTSv2: klonowanie głosu |
| **VLM** | Moondream2 (domyślny) / LLaVA | Moondream2: ~1.5 GB VRAM, wystarczający do analizy scen |
| **OCR** | EasyOCR (CUDA) | Ekstrakcja tekstu z UI gier (itemy, statystyki) |
| **Screen Capture** | DXcam | Najszybsza metoda na Windows (DirectX), minimalny FPS impact |
| **Input** | pynput | Globalna obsługa klawiszy/myszy (PTT, hotkeys) |
| **DB** | SQLite + ChromaDB/LanceDB | Historia konwersacji + pamięć semantyczna |
| **Kompresja** | py7zr (fallback: zipfile) | Archiwizacja logów (.7z) |
| **Config watch** | watchdog | Hot-reload plików konfiguracyjnych |
| **Math** | asteval | Bezpieczna ewaluacja wyrażeń matematycznych (MCP calculator) |
| **Web search** | DuckDuckGo / SearXNG | Prywatne, darmowe, bez klucza API |
| **Doc Gen** | markdown2 / mistune | Konwersja Markdown do HTML dla raportów |

---

## 3. Wzorce Architektoniczne

### 3.1 Strategy/Adapter Pattern — Komponenty AI

Każdy komponent AI implementuje wspólny interfejs:

```python
# Interfejsy bazowe
class BaseLLMClient(ABC):
    async def chat(self, messages, tools=None) -> Response: ...
    async def stream(self, messages, tools=None) -> AsyncIterator: ...

class BaseSTTEngine(ABC):
    async def transcribe(self, audio_data) -> TranscriptionResult: ...

class BaseTTSEngine(ABC):
    async def synthesize(self, text, emotion=None) -> AudioData: ...

class BaseVLMAnalyzer(ABC):
    async def analyze(self, image, prompt) -> str: ...

class StorageBackend(ABC):
    async def save_conversation(self, entry) -> None: ...
    async def get_history(self, limit) -> List[Entry]: ...
    async def search_semantic(self, query, k) -> List[Entry]: ...
```

Implementacje: `LMStudioClient`, `FasterWhisperEngine`, `PiperTTSEngine`, `Moondream2Analyzer`, `SqliteBackend`, `PostgresBackend`.

### 3.2 Repository Pattern — Persystencja

```python
class ConversationRepository:
    def __init__(self, backend: StorageBackend): ...

class PlayerProfileRepository:
    # YAML-based, no DB needed
    def load(self) -> PlayerProfile: ...
    def save(self, profile: PlayerProfile) -> None: ...
```

### 3.3 Circuit Breaker Pattern

```python
class CircuitBreaker:
    states: CLOSED, OPEN, HALF_OPEN
    failure_threshold: 3
    recovery_timeout: 30  # seconds
    
    async def call(self, func) -> Result:
        if self.state == OPEN:
            if time_since_last_failure > recovery_timeout:
                self.state = HALF_OPEN  # try one call
            else:
                raise ServiceUnavailable
```

### 3.4 Jednoprocesowa Architektura

```
Jeden proces Python:
├── asyncio event loop (FastAPI)
│   ├── HTTP endpoints
│   ├── WebSocket connections
│   ├── Observer loop (async task)
│   ├── Daily scheduler (async task)
│   └── Config file watcher (async task)
│
├── ThreadPoolExecutor (CPU-bound)
│   ├── STT inference
│   ├── VLM inference
│   ├── TTS generation
│   └── OCR processing
│
└── asyncio.Queue (bufor między wątkami)
    ├── audio_queue (STT → orkiestrator)
    ├── response_queue (LLM → TTS)
    └── emotion_queue (parser → frontend WebSocket)
```

---

## 4. Przepływy Danych

### 4.1 Interakcja Głosowa (PTT)

```
User przytrzymuje klawisz PTT
       │
       ▼
pynput → Audio Recording (mikrofon)
       │
User zwalnia PTT
       │
       ▼
Audio → [GPU Scheduler: priorytet 1]
       │
       ▼
Faster-Whisper STT → tekst + confidence
       │
       ├─ confidence < 0.4 → "Nie zrozumiałem" + [EMO:confused]
       ├─ confidence 0.4-0.7 → "Czy chodziło o: [tekst]?"
       │
       ▼ confidence > 0.7
Command Matcher (regex)
       │
       ├─ Match → Natychmiastowa akcja (bez LLM)
       │
       ▼ No match
Prompt Builder:
  base + persona + [game_profile] + [observer_ctx] + [player_profile]
       │
       ▼
LM Studio API (function calling)
       │
       ├─ Tool call → MCP Tool → wynik → powrót do LLM
       │
       ▼
Response + [EMO:tag]
       │
       ├─ Emotion Parser → WebSocket → Frontend (awatar)
       │
       ▼
[GPU Scheduler: priorytet 3]
       │
       ▼
TTS (Piper) → audio stream
       │
       ▼
WebSocket → Frontend (lip-sync + audio playback)
```

### 4.2 Observer Loop (Gra)

```
Wykryto proces gry + komenda "Obserwuj"
       │
       ▼
  ┌─── Loop co N sekund ────────────────────┐
  │                                          │
  │  DXcam → screenshot                     │
  │       │                                  │
  │       ▼                                  │
  │  [GPU Scheduler: priorytet 4]            │
  │       │                                  │
  │       ▼                                  │
  │  VLM (Moondream2) → opis sceny          │
  │       │                                  │
  │       ├─ Tooltip/item detected?          │
  │       │   └─ Crop → OCR → tekst stats   │
  │       │                                  │
  │       ▼                                  │
  │  Prompt: game_profile + opis + [OCR]    │
  │       │                                  │
  │       ▼                                  │
  │  LM Studio → komentarz + [EMO:tag]     │
  │       │                                  │
  │       ▼                                  │
  │  Ping dźwiękowy → TTS → audio           │
  │       │                                  │
  │       ▼                                  │
  │  WebSocket → lip-sync + emocja          │
  │                                          │
  └─── Sprawdź: PTT aktywny? → PAUSE ───────┘
```

### 4.3 On-demand Screen Query

```
User: "Co widzisz na ekranie?" / "O czym jest ta strona?"
       │
       ▼
STT → Command Matcher: nie pasuje → LLM
       │
LLM rozpoznaje intencję "screen query"
       │
       ▼
DXcam: full screenshot + crop 600x400 wokół kursora
       │
       ▼
VLM: analiza obu obrazów z promptem:
  "Kursor w pozycji (X,Y). Skup się na elemencie pod kursorem."
       │
       ▼
Wynik VLM → LLM → odpowiedź kontekstowa
```

---

## 5. Struktura Katalogów

### 5.1 Content Root (`c:\ai\asystent`)

```
c:\ai\asystent\
├── config\
│   ├── config.yaml                 # Główna konfiguracja
│   ├── commands.yaml               # Komendy systemowe
│   └── game_profiles\
│       ├── poe2.yaml
│       └── stellaris.yaml
├── models\
│   ├── avatar\
│   │   └── default.vrm             # Domyślny model VRM
│   ├── stt\                         # Faster-Whisper
│   ├── tts\                         # Piper / XTTSv2
│   └── vlm\                         # Moondream2 / LLaVA
├── personas\
│   ├── default.md                   # Sarkastyczny kompan
│   └── komentator.md
├── knowledge\
│   └── poe2\
│       └── season2_meta.md
├── documents\                       # Wygenerowane raporty
│   ├── session_report_2026-04-25.md
│   └── build_comparison.html
├── data\
│   ├── conversations.db             # SQLite
│   ├── memory\                      # ChromaDB/LanceDB
│   ├── player_profile.yaml
│   └── mcp_cache\                   # Cache MCP (SQLite)
├── logs\
│   ├── sessions\
│   │   └── 2026-04-25_session1.md
│   ├── system_status.log
│   └── archive\                     # .7z skompresowane
├── backups\                         # Backup ZIP
├── templates\
│   └── report_template.html
└── debug\
    └── screenshots\
```

### 5.2 Source Code (`c:\code\_repos\antigravity\assystent`)

```
assystent\
├── docs\                            # PRD, PROJECT_PLAN
├── backend\
│   ├── main.py                      # FastAPI entry point
│   ├── core\
│   │   ├── orchestrator.py
│   │   ├── prompt_builder.py
│   │   ├── emotion_parser.py
│   │   ├── command_matcher.py
│   │   ├── gpu_scheduler.py
│   │   ├── circuit_breaker.py
│   │   └── session_watchdog.py
│   ├── ai\
│   │   ├── interfaces.py            # Base classes
│   │   ├── llm_client.py
│   │   ├── stt_engine.py
│   │   ├── tts_engine.py
│   │   ├── vlm_analyzer.py
│   │   └── ocr_engine.py
│   ├── mcp\
│   │   ├── web_search.py
│   │   ├── web_scraper.py
│   │   ├── calculator.py
│   │   ├── time_tool.py
│   │   ├── document_generator.py
│   │   └── screen_capture.py
│   ├── memory\
│   │   ├── interfaces.py
│   │   ├── sqlite_backend.py
│   │   ├── chromadb_backend.py
│   │   └── player_profile.py
│   ├── observer\
│   │   ├── game_detector.py
│   │   ├── observer_loop.py
│   │   └── screen_analyzer.py
│   ├── config\
│   │   ├── loader.py
│   │   └── watcher.py
│   └── tests\
│       ├── mocks\
│       ├── unit\
│       └── integration\
├── frontend\
│   ├── src\
│   │   ├── components\
│   │   │   ├── Avatar3D.jsx
│   │   │   ├── ConfigPanel.jsx
│   │   │   └── StatusOverlay.jsx
│   │   ├── hooks\
│   │   ├── utils\
│   │   └── App.jsx
│   ├── public\
│   └── electron\
│       └── main.js
├── requirements.txt
├── package.json
└── README.md
```

---

## 6. Konfiguracja Główna

```yaml
# config/config.yaml

general:
  language: pl                        # pl | en
  proactivity_level: moderate         # passive | moderate | active
  quiet_hours: ["23:00", "07:00"]
  content_root: "c:\\ai\\asystent"

audio:
  input_device: default
  output_device: default
  tts_volume: 0.8
  stt_confidence_threshold: 0.7
  stt_low_confidence_threshold: 0.4
  notification_sound: true

observer:
  default_interval_seconds: 10
  ambient_enabled: false
  log_observer_comments: true

ai:
  lm_studio_url: "http://localhost:1234/v1"
  default_model: "gemma-4-e4b"
  max_tool_calls_per_turn: 5
  streaming: true

models:
  stt: "faster-whisper-medium"
  tts: "piper"                        # piper | xttsv2
  vlm: "moondream2"                   # moondream2 | llava
  models_path: "c:\\ai\\asystent\\models"

storage:
  backend: sqlite                     # sqlite | postgres | gcp_firestore
  data_path: "c:\\ai\\asystent\\data"
  archive_days: 90
  semantic_memory_limit: 10000
  log_compression: 7z                 # 7z | zip | none

documents:
  output_path: "c:\\ai\\asystent\\documents"
  default_format: md                  # md | html
  auto_session_report: false
  html_theme: dark                    # dark | light
  html_diagrams: mermaid              # mermaid | ascii | none

mcp:
  web_search_rate_limit: 10           # req/min
  cache_ttl_game_meta: 86400          # 24h in seconds
  cache_ttl_general: 3600             # 1h
  cache_ttl_scraper: 604800           # 7 days
  daily_check_on_startup: true

debug:
  enabled: false
  save_screenshots: false
  log_pipeline: false
  overlay_status: false

persona:
  active: "default"                   # nazwa pliku w personas/
```

---

## 7. Komunikacja Frontend ↔ Backend

### 7.1 WebSocket

| Event | Kierunek | Dane |
|-------|----------|------|
| `audio_stream` | Backend → Frontend | PCM audio data (TTS output) |
| `emotion` | Backend → Frontend | `{ emotion: "excited", intensity: 0.8 }` |
| `status` | Backend → Frontend | `{ state: "listening", health: "healthy" }` |
| `text_overlay` | Backend → Frontend | `{ text: "..." }` (tryb cichy) |
| `config_update` | Backend → Frontend | Zmiana konfiguracji (hot-reload) |

Heartbeat: ping co 5s. Brak pong przez 15s → disconnect. Auto-reconnect z state sync.

### 7.2 REST API

| Endpoint | Metoda | Opis |
|----------|--------|------|
| `/status` | GET | Stan systemu (health, VRAM, wątki) |
| `/config` | GET/PUT | Odczyt/zapis konfiguracji |
| `/debug/last_interaction` | GET | Pipeline ostatniej interakcji (debug) |
| `/observer/start` | POST | Start obserwatora |
| `/observer/stop` | POST | Stop obserwatora |

### 7.3 Backend bez Frontendu

Jeśli frontend rozłączony: backend kontynuuje. TTS odtwarza audio bezpośrednio (bez lip-sync). Obserwator działa. Przy reconnect: auto-sync stanu.

---

*Następny dokument: [PRD 05: UX i Zachowanie](PRD_05_UX_BEHAVIOR.md)*
