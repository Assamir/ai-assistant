# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

**Assystent** is a local AI gaming assistant: Python/FastAPI backend + Electron/React/Three.js frontend. It runs entirely offline-first (LLM via LM Studio on localhost:1234), with a 3D VRM avatar, voice pipeline (STT→LLM→TTS), and a game observer loop.

- **Content root at runtime:** `c:\ai\asystent` (user data, models, config) — separate from this source repo
- **Source repo:** `c:\code\_repos\antigravity\assystent`
- **Language:** The assistant communicates in **Polish**. All command patterns, LLM prompts, system messages, and handler responses are in Polish. This is intentional and pervasive — do not "fix" Polish strings.
- **Default assistant name:** `Aria` (from `config.general.assistant_name`).

---

## Environment Setup

```bash
# Create and activate Python virtual environment (Windows)
python -m venv .venv
.venv\Scripts\activate

# Core dependencies
pip install -r requirements.txt

# Optional: adds EasyOCR for screen text recognition
pip install -r requirements-vision.txt
```

Optional extras (install into the same venv):

| Package | Enables |
|---------|---------|
| `pynput` | Backend global PTT hotkey (`audio.backend_ptt_listener_enabled`) |
| `openwakeword` | Wakeword detection (`audio.wakeword_enabled`) |
| `torch torchvision transformers accelerate` | Moondream2 VLM (`vlm.enabled: true`) |
| `dxcam` | Fastest Windows screen capture (DXGI); without it, falls back to mss then pyautogui |

---

## Backend Commands

```bash
# Run the backend server (from repo root, with venv active)
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Run all tests
pytest

# Run a single test file
pytest tests/unit/test_emotion_parser.py

# Run a single test by name
pytest tests/unit/test_emotion_parser.py::test_parse_happy -v

# Run only unit tests (fast, no real models)
pytest tests/unit/

# Run integration tests (use mock engines, no real LM Studio needed)
pytest tests/integration/

# Verify environment dependencies
python scripts/verify_env.py
```

`pytest.ini` sets `asyncio_mode = auto` and `pythonpath = .`, so all async tests work without extra decoration and imports resolve from repo root.

## Frontend Commands

```bash
cd frontend

# Dev server (Vite, no Electron shell)
npm run dev

# Run with Electron shell (full app)
ASSYSTENT_DEV=1 npm run electron

# Build distributable (client-only — no bundled Python)
npm run electron:dist:client

# Build distributable (full — with bundled Python app)
npm run electron:dist:full
```

Frontend environment overrides (Vite):

| Variable | Purpose |
|----------|---------|
| `VITE_API_BASE_URL` | Backend HTTP base URL (default: `http://127.0.0.1:8000`) |
| `VITE_WS_URL` | WebSocket URL (default: derived from `window.location`) |
| `VITE_VRM_URL` | VRM model path |
| `VITE_CONFIG_PUT_TOKEN` | Token for `PUT /api/v1/config` |

In Electron, `electron-main.cjs` injects `window.assystent = { wsUrl, apiUrl, vrmUrl, configPutToken }` to pass config into the renderer without env vars.

---

## Architecture

### Backend

`backend/main.py` is the FastAPI entry point. The `lifespan` context manager starts/stops all long-running services in order. `create_app_context()` in `backend/api/app_context.py` is the composition root — it wires together every service into a single `AppContext` dataclass that is attached to `app.state.ctx`.

Key layers:

| Layer | Location | Role |
|-------|----------|------|
| **Config** | `backend/config/` | `ConfigLoader` reads YAML from content_root, merges with env vars (`ASSY_` prefix). `ConfigSchema` is the Pydantic V2 model. |
| **AI Adapters** | `backend/ai/` | Concrete implementations of abstract interfaces: `FasterWhisperSTT`, `PiperTTS`, `LMStudioClient`, `Moondream2VLM`, `EasyOCREngine`, `DesktopScreenCapture`. Each is optional — missing packages degrade gracefully (returns `None` from `try_build_*` helpers). |
| **Core Abstractions** | `backend/core/interfaces.py` | `BaseLLMClient`, `BaseSTTEngine`, `BaseTTSEngine`, `BaseVLMAnalyzer`, `BaseOCREngine`, `BaseScreenCapture`, `CircuitBreaker`, `GPUScheduler`. Tests mock against these. |
| **Orchestrator** | `backend/core/orchestrator.py` | `ConversationOrchestrator` runs the full turn: command matching → prompt building → LLM call → tool execution loop (max 5 calls) → emotion parsing → TTS. |
| **MCP Tools** | `backend/mcp/` | `ToolRegistry` holds tools. `build_default_tool_registry()` registers tools; **`web_search`** i **`web_scraper`** są zawsze w rejestrze (LLM zawsze może wywołać sieć — degradacja przy braku połączenia). `mcp.enabled` steruje wyłącznie **`generate_document`**. `register_context_dependent_mcp_tools()` dodaje `screen_capture`. Lista `mcp.tools_enabled` nie usuwa narzędzi sieciowych ani `get_current_time`/`calculator`. |
| **Memory** | `backend/memory/` | `SemanticRecall` wraps ChromaDB. `KnowledgeIngester` chunks `.md` files from `knowledge/`. Enabled/disabled via `config.memory.enabled`. |
| **Services** | `backend/services/` | `GameObserver` (process-based game detection + VLM fallback), `ObserverLoop` (periodic capture→comment cycle), `VoicePipeline`, `SessionWatchdog`, `PlayerProfileRepository`, `DailyMetaCheck`. |
| **API** | `backend/api/` | `routes.py` (REST under `/api/v1`), `ws_router.py` (WebSocket at `/ws`), `WebSocketManager` (multiplexes events by session UUID). |
| **DB** | `backend/db/` | SQLite via `aiosqlite`. `MigrationRunner` applies numbered SQL files from `backend/db/migrations/`. `repositories.py` contains all repository classes. |

### GPU Scheduler

`GPUScheduler` (in `backend/core/interfaces.py`) enforces serial GPU access via `asyncio.PriorityQueue` + semaphore. Priority 1 = STT, 2 = LLM, 3 = TTS, 4 = VLM observer.

### Voice Pipeline

`PTTHotkeyListener` (pynput, backend process) → `VoiceInputCoordinator` → `FasterWhisperSTT` → `ConversationOrchestrator` → `PiperTTS` → PCM chunks over WebSocket `audio_stream` events → frontend `AudioContext`.

### Observer Loop

`ObserverLoop` runs on a configurable interval. Each cycle: `DesktopScreenCapture` takes a screenshot → `SceneDeduper` computes dHash to skip unchanged frames → `DualVisionPipeline` (VLM + OCR) analyzes the screen → `ConversationOrchestrator` generates a comment → TTS or `text_overlay`. Screen capture falls back: DXcam (DXGI) → mss → pyautogui.

### Frontend

Electron app in `frontend/`. React + Three.js + `@pixiv/three-vrm`. Main process: `electron-main.cjs`. Two windows: transparent frameless avatar window (always-on-top) and a standard config panel window. WebSocket client reconnects with exponential backoff (1s→30s). Audio is played through Web Audio API `AudioContext`; PTT duck is a `GainNode` ramp.

### Config system

Config is loaded from `{content_root}/config/config.yaml` merged over Pydantic defaults. Environment variable prefix is `ASSY_`, nested delimiter `__` (e.g. `ASSY_LLM__BASE_URL`). Hot-reload watches the YAML file with `watchdog`; most keys apply instantly, some (STT/TTS model paths) require restart.

---

## Content Root Structure

At runtime, `{content_root}` (default `c:\ai\asystent`) holds:

```
config/config.yaml          — main config (created manually or via PUT /api/v1/config)
personas/{name}.md          — persona files (YAML frontmatter + markdown body)
game_profiles/{id}.yaml     — per-game profiles (process_names, context_prompt, observer_interval_seconds)
knowledge/*.md              — documents ingested into ChromaDB for semantic recall
data/player_profile.yaml    — per-game league, version, characters (managed by PlayerProfileRepository)
data/chroma/                — ChromaDB persistent store (when memory.chroma_persist: true)
data/assystent.db           — SQLite database
```

Game profile loading priority: `KNOWN_GAMES` built-ins → `game_profiles/*.yaml` files → `config.game_profiles` inline YAML. Later entries override earlier ones.

---

## Command System

Before every LLM call, `CommandMatcher.match_all_segments()` checks whether the user's text matches a builtin or custom command. If it matches, the LLM is bypassed entirely. Text is normalized: lowercased, diacritics stripped (`ł→l`), punctuation removed.

20 builtin commands (CMD-01..CMD-20) are defined as compiled regexes in `backend/core/command_matching.py`. Each maps to a `builtin_action` string dispatched via `_builtin_registry` in `backend/core/command_handlers.py`. Handlers mutate `orchestrator.state` and/or emit side-effect events. Examples: `sleep/wake`, `observer_start/stop`, `silent_mode_on/off`, `change_persona`, `check_league_hint`, `daily_check`.

Custom commands (from `config.yaml` or registered at runtime) follow the same priority queue but dispatch to a named MCP tool instead of a builtin handler.

Cooldowns are tracked in `CooldownTracker` (in-memory, per `cmd_id`). Fuzzy fallback (Levenshtein) only applies to CMD-01 (sleep).

---

## Orchestrator State

`orchestrator.state` is the shared runtime dict read and written by command handlers, observer, and API routes. Important keys:

| Key | Set by | Effect |
|-----|--------|--------|
| `sleeping` | sleep/wake handlers | Suppresses LLM turns and observer |
| `observer_active` | observer_start/stop handlers | Gates `ObserverLoop.run_cycle()` |
| `observer_paused` | sleep handler, `ObserverPauseManager` | Pauses observer without stopping it |
| `silent_mode` | silent_mode_on/off handlers | Observer sends `text_overlay` instead of TTS |
| `current_game` | `GameObserver` emit | Display name of detected game |
| `current_game_profile_id` | `GameObserver` emit | `GameProfile.id` used to look up profile |
| `active_persona` | change_persona handler | Which persona file `PersonaLoader` loads |
| `last_observer_comment` | `ObserverLoop` | Deduplicated by `SequenceMatcher` before emit |
| `manual_game_profile_id` | manual_game_set handler | Overrides psutil detection |
| `manual_game_profile_lock` | manual_game_set/clear handlers | Disables automatic process scanning |
| `observer_interval_seconds` | set_interval handler | Per-session override of `cycle_interval_seconds` |

---

## WebSocket Protocol

The WS at `/ws` exchanges JSON frames: `{"event": "<name>", "payload": {...}}`.

### Backend → Frontend events

| Event | Payload keys | Purpose |
|-------|-------------|---------|
| `visual_state` | `state` (idle/listening/thinking/speaking) | Drives avatar animation |
| `emotion` | `emotion` | Sets avatar facial expression |
| `assistant_reply_text` | `text` | Full assistant response text (before audio chunks) |
| `stt_result` | `text`, `hint` | STT transcription result; `hint` carries error codes like `stt_unconfigured` |
| `observer_comment` | `text`, `emotion`, `game` | Observer proactive comment |
| `audio_stream` | `chunk_base64` | Base64-encoded raw PCM audio chunks (streamed TTS) |
| `audio_duck` | `target_volume`, `ramp_ms` | PTT ducking ramp signal |
| `text_overlay` | `text` | Silent-mode text display |
| `agent_activity` | `phase`, `tool`, `arguments_preview` | Tool call progress indicator |
| `game_detected` | `game`, `game_id`, `active` | Game start/stop broadcast |
| `system_state` | `state`, `health` | Hibernation / resume notifications |
| `player_profile.league_hint` | `game_id`, `mismatch_hint`, etc. | League change suggestion |
| `player_profile.league_changed` | `game`, `previous_league`, `league` | After PATCH to player-profile |

### Frontend → Backend frames

| Event | Payload keys | Purpose |
|-------|-------------|---------|
| `chat_text` | `text` | Send a text message to the orchestrator |
| `ptt_start` | _(empty)_ | Signals microphone recording start (triggers visual state change) |
| `ptt_end` | `audio` (base64 WAV, optional) | End recording; backend runs STT→LLM→TTS if audio present |
| `ping` | _(empty)_ | Keepalive / connectivity check |
| `frontend_ready` | _(empty)_ | Sent after connection opens; backend may emit initial state |

---

## REST API Surface

All routes are prefixed `/api/v1` (defined in `backend/api/routes.py`).

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/status` | Full health snapshot with component details |
| GET | `/health` | Minimal health check |
| GET/PUT | `/config` | Read or patch config.yaml (PUT requires `X-Config-Put-Token` header when `ASSYSTENT_CONFIG_PUT_TOKEN` env var is set) |
| GET | `/tools` | List registered MCP tools |
| POST | `/voice/chat` | Text-in / text-out (supports SSE streaming) |
| POST | `/voice/synthesize` | TTS: text → WAV |
| POST | `/voice/transcribe` | STT: audio file → text + confidence |
| POST | `/voice/process` | STT + chat + TTS pipeline: audio → WAV |
| GET/PATCH | `/player-profile` | Read / update per-game league and version |
| POST | `/player-profile/games/{game}/archive` | Archive a season entry |
| POST | `/player-profile/games/{game}/check-league-hint` | Trigger league hint check |
| POST | `/daily-checks/run` | Force or throttled daily meta check |
| GET | `/daily-checks` | List recent daily check records |

---

## Testing Conventions

- **All AI components are optional** — tests never require real models. `AppContext` fields like `stt_engine`, `tts_engine`, `vlm_engine` can be `None`.
- **SQLite tests** use `migrated_db_path` fixture (temp file + migrations applied, defined in `tests/conftest.py`). ChromaDB tests use `chromadb.EphemeralClient()`.
- **Async tests** work without `@pytest.mark.asyncio` because `asyncio_mode = auto` is set in `pytest.ini`.
- **Slow/real-LLM tests** should be marked `@pytest.mark.slow` and skipped in CI.
- Game screenshot fixtures go in `tests/fixtures/images/poe2/` and `tests/fixtures/images/stellaris/`.

---

## Key Conventions

- **Emotion tags:** LLM responses begin with `[EMO:name]` (one of 16 emotions: `happy`, `amused`, `proud`, `sympathetic`, `sad`, `disappointed`, `angry`, `disgusted`, `excited`, `scared`, `surprised`, `nervous`, `thinking`, `confused`, `nostalgic`, `sarcastic`). `parse_emotion_tag()` in `backend/core/emotion_parser.py` strips the tag before TTS.
- **Observer `[SKIP]`:** Observer comment prompts return the literal string `[SKIP]` when the scene is uninteresting — the orchestrator detects this and suppresses TTS.
- **Sandbox:** `backend/mcp/sandbox.py` — all file I/O in MCP tools validates that paths stay inside `content_root`.
- **MCP cache key:** `SHA256(tool_name + canonical_json(params))` — sorted keys, no whitespace. See `backend/mcp/cache_key.py`.
- **DB migrations:** Add numbered SQL files to `backend/db/migrations/` (e.g. `003_*.sql`). `MigrationRunner` applies them in order on startup.
- **New AI adapter:** Subclass the relevant `Base*` ABC from `backend/core/interfaces.py`, add a `try_build_*` helper in `backend/api/app_context.py`, wire into `create_app_context()`.
- **New MCP tool:** Implement and register in `backend/mcp/registry.py` or `backend/mcp/context_tools.py` (for tools needing `AppContext`).
- **LM Studio FC mirror:** `ai_runtime.mirror_tool_results_as_user: true` duplicates every `role=tool` message as a `role=user` message — a workaround for local models (e.g. some Gemma presets) that ignore tool results in standard format.
- **ConversationStore:** Keeps the last 40 messages per session (keyed by WS session UUID or REST `session_id`).

---

## Pre-implementation Documentation

All design documentation lives in `docs/`. The pre-implementation plan (`docs/PRE_IMPLEMENTATION_PLAN.md`) describes 16 specification documents (DOK-01–16). Completed docs are in `docs/`. `docs/DECISIONS_LOG.md` is the single source of truth for all architectural decisions — attach it when writing new spec documents.
