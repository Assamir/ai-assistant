# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

**Assystent** is a local AI gaming assistant: Python/FastAPI backend + Electron/React/Three.js frontend. It runs entirely offline-first (LLM via LM Studio on localhost:1234), with a 3D VRM avatar, voice pipeline (STT→LLM→TTS), and a game observer loop.

- **Content root at runtime:** `c:\ai\asystent` (user data, models, config) — separate from this source repo
- **Source repo:** `c:\code\_repos\antigravity\assystent`

---

## Backend Commands

```bash
# Run the backend server (from repo root)
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
npm run electron

# Build distributable (client-only — no bundled Python)
npm run electron:dist:client

# Build distributable (full — with bundled Python app)
npm run electron:dist:full
```

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
| **MCP Tools** | `backend/mcp/` | `ToolRegistry` holds 6 tools. `build_default_tool_registry()` wires them. Context-dependent tools (screen_capture, player_profile) are registered after `AppContext` exists via `register_context_dependent_mcp_tools()`. |
| **Memory** | `backend/memory/` | `SemanticRecall` wraps ChromaDB. `KnowledgeIngester` chunks `.md` files from `knowledge/`. Enabled/disabled via `config.memory.enabled`. |
| **Services** | `backend/services/` | `GameObserver` (process-based game detection + VLM fallback), `ObserverLoop` (periodic capture→comment cycle), `VoicePipeline`, `SessionWatchdog`, `PlayerProfileRepository`, `DailyMetaCheck`. |
| **API** | `backend/api/` | `routes.py` (REST under `/api/v1`), `ws_router.py` (WebSocket at `/ws`), `WebSocketManager` (multiplexes events by session UUID). |
| **DB** | `backend/db/` | SQLite via `aiosqlite`. `MigrationRunner` applies numbered SQL files from `backend/db/migrations/`. `repositories.py` contains all repository classes. |

### GPU Scheduler

`GPUScheduler` (in `backend/core/interfaces.py`) enforces serial GPU access via `asyncio.PriorityQueue` + semaphore. Priority 1 = STT, 2 = LLM, 3 = TTS, 4 = VLM observer.

### Voice Pipeline

`PTTHotkeyListener` (pynput, backend process) → `VoiceInputCoordinator` → `FasterWhisperSTT` → `ConversationOrchestrator` → `PiperTTS` → PCM chunks over WebSocket `audio_stream` events → frontend `AudioContext`.

### Frontend

Electron app in `frontend/`. React + Three.js + `@pixiv/three-vrm`. Main process: `electron-main.cjs`. Two windows: transparent frameless avatar window (always-on-top) and a standard config panel window. WebSocket client reconnects with exponential backoff (1s→30s). Audio is played through Web Audio API `AudioContext`; PTT duck is a `GainNode` ramp.

### Config system

Config is loaded from `{content_root}/config/config.yaml` merged over Pydantic defaults. Environment variable prefix is `ASSY_`, nested delimiter `__` (e.g. `ASSY_LLM__BASE_URL`). Hot-reload watches the YAML file with `watchdog`; most keys apply instantly, some (STT/TTS model paths) require restart.

---

## Testing Conventions

- **All AI components are optional** — tests never require real models. `AppContext` fields like `stt_engine`, `tts_engine`, `vlm_engine` can be `None`.
- **SQLite tests** use `migrated_db_path` fixture (temp file + migrations applied). ChromaDB tests use `chromadb.EphemeralClient()`.
- **Async tests** work without `@pytest.mark.asyncio` because `asyncio_mode = auto` is set in `pytest.ini`.
- **Slow/real-LLM tests** should be marked `@pytest.mark.slow` and skipped in CI.
- Game screenshot fixtures go in `tests/fixtures/images/poe2/` and `tests/fixtures/images/stellaris/`.

---

## Key Conventions

- **Emotion tags:** LLM responses begin with `[EMO:name]` (one of 16 emotions). `parse_emotion_tag()` in `backend/core/emotion_parser.py` strips the tag before TTS and returns the emotion name.
- **Observer `[SKIP]`:** Observer comment prompts return the literal string `[SKIP]` when the scene is uninteresting — the orchestrator detects this and suppresses TTS.
- **Sandbox:** `backend/mcp/sandbox.py` — all file I/O in MCP tools validates that paths stay inside `content_root`.
- **MCP cache key:** `SHA256(tool_name + canonical_json(params))` — sorted keys, no whitespace. See `backend/mcp/cache_key.py`.
- **DB migrations:** Add numbered SQL files to `backend/db/migrations/` (e.g. `003_*.sql`). `MigrationRunner` applies them in order on startup.
- **New AI adapter:** Subclass the relevant `Base*` ABC from `backend/core/interfaces.py`, add a `try_build_*` helper in `backend/api/app_context.py`, wire into `create_app_context()`.
- **New MCP tool:** Implement and register in `backend/mcp/registry.py` or `backend/mcp/context_tools.py` (for tools needing `AppContext`).

---

## Pre-implementation Documentation

All design documentation lives in `docs/`. The pre-implementation plan (`docs/PRE_IMPLEMENTATION_PLAN.md`) describes 16 specification documents (DOK-01–16). Completed docs are in `docs/`. `docs/DECISIONS_LOG.md` is the single source of truth for all architectural decisions — attach it when writing new spec documents.
