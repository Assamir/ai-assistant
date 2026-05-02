# DOK-14: DEFINITION_OF_DONE.md — Kryteria Akceptacji per Faza

> **Status:** v1.0 — 2026-05-02
> **Materiały źródłowe:** PRD_06_IMPLEMENTATION.md, TEST_PLAN.md

---

## Faza 1 — Backend Core (MVP-1)

### A) Code Complete

- [ ] FastAPI app startuje (`uvicorn backend.main:app`)
- [ ] Config loader: defaults < yaml < env, walidacja, zapis normalized
- [ ] Interfejsy bazowe: `BaseLLMClient`, `BaseSTTEngine`, `BaseTTSEngine`, `BaseVLMAnalyzer`
- [ ] `GPUScheduler` — priority queue z mutex, aging
- [ ] `CircuitBreaker` — 3 states, persistence, TTL
- [ ] `LMStudioClient` — streaming, function calling, circuit breaker
- [ ] `FasterWhisperSTT` — confidence thresholds, GPU scheduler
- [ ] `PiperTTS` — subprocess, emotion modulation (speed/pitch)
- [ ] `WakewordDetector` — openWakeWord, fallback "Hey Jarvis"
- [ ] `AudioCapture` — PTT (pynput), wakeword switch
- [ ] `Orchestrator` — voice→command?→LLM→TTS pipeline
- [ ] `PromptBuilder` — section assembly, token budget trimming
- [ ] `EmotionParser` — `[EMO:tag]` extraction + validation
- [ ] `CommandMatcher` — regex exact + fuzzy (Levenshtein ≤ 2)
- [ ] 16 builtin command handlers
- [ ] `SessionWatchdog` — hibernation detection, crash recovery
- [ ] REST API: `/health`, `/status`, `/config`
- [ ] WebSocket: multiplexed events (emotion, audio, state)
- [ ] MCP: `get_current_time`, `calculator`
- [ ] SQLite: 14 tabel, migration runner, WAL mode
- [ ] File watcher: hot-reload config + personas

### B) Testy

- [ ] ≥80% unit test coverage (backend/core)
- [ ] Testy GPU-T-01→04, CB-T-01→06, WD-T-01→04 passing
- [ ] Testy CMD-T-01→11 passing
- [ ] ≥8 integration testów API passing
- [ ] Brak failing tests w `pytest tests/`

### C) Performance

- [ ] FPS impact < 5% (z grą vs bez)
- [ ] PTT→first audio < 3s (benchmark)
- [ ] Latency measurement documented

### D) Acceptance Demos (manual)

- [ ] Demo 1: PTT → mówisz "Która godzina?" → asystent odpowiada głosem z poprawnym czasem
- [ ] Demo 2: PTT → "Ile to jest 450 plus 78 razy 1.35?" → poprawna odpowiedź
- [ ] Demo 3: PTT → "Idź spać" → odpowiedź + state change
- [ ] Demo 4: PTT → "Obudź się" → przywrócenie
- [ ] Demo 5: Zmiana `config.yaml` → asystent mówi "Przeładowałem konfigurację"
- [ ] Demo 6: Kill backend → restart → crash detection log

---

## Faza 2 — Vision, MCP, Memory (MVP-2)

### A) Code Complete

- [ ] `ScreenCapture` — DXcam + pyautogui fallback
- [ ] `Moondream2VLM` — GPU scheduler P4
- [ ] `EasyOCR` — dual pipeline (VLM+OCR), trigger keywords
- [ ] `GameDetector` — kaskadowy: process→VLM→manual
- [ ] `GameProfile` loader + hot-reload
- [ ] `ObserverLoop` — skip conditions, backpressure, pause/resume
- [ ] `CommentRateLimiter`, diversity check (cosine)
- [ ] `web_search` — DuckDuckGo + rate limiter + cache
- [ ] `web_scraper` — trafilatura + Playwright fallback
- [ ] `generate_document` — MD + HTML (dark theme)
- [ ] `screen_capture` tool — on-demand + cursor crop
- [ ] `SandboxValidator` — path + URL validation
- [ ] `MCPCache` — SHA256 keys, TTL per tool, stampede prevention
- [ ] ChromaDB: 2 kolekcje (conversations, knowledge_base)
- [ ] `SemanticRecall` — embed, query, dedup
- [ ] `KnowledgeIngester` — chunking, folder watcher, re-ingestion
- [ ] `PlayerProfileRepository` — YAML source, snapshots
- [ ] ChromaDB FIFO rotation (10k limit)
- [ ] Backup/restore (zip), auto-archive logs (.7z)
- [ ] Daily meta check, season reset detection
- [ ] Online mode detector (30s interval)

### B) Testy

- [ ] Testy OBS-T-01→04, RL-T-01→03, CACHE-T-01→04 passing
- [ ] Testy MCP-T-01→13 passing
- [ ] Integration: observer→VLM→comment→TTS→DB
- [ ] Integration: web_search→cache→LLM→document

### C) Acceptance Demos

- [ ] Demo 1: Uruchom PoE2 → "Zacznij obserwować" → komentarz głosowy
- [ ] Demo 2: "Co widzisz na ekranie?" → analiza VLM+OCR
- [ ] Demo 3: "Jaki jest topowy build LA?" → web_search → odpowiedź
- [ ] Demo 4: "Porównaj buildy LA i TS, zrób raport HTML" → dokument
- [ ] Demo 5: "Gram teraz TankMasterem" → zmiana profilu
- [ ] Demo 6: "Zrób backup" → ZIP w backups/

---

## Faza 3 — Frontend + Avatar (Release)

### A) Code Complete

- [ ] Electron: frameless, transparent, AOT, system tray
- [ ] React: Avatar3D component, Config Panel, Setup Wizard
- [ ] Three.js + three-vrm: VRM loading, capabilities scan
- [ ] 16 emocji: blendshapes + aura + body animations
- [ ] Emotion state machine: blend-in, hold, fade-out, conflict resolution
- [ ] Lip-sync: Web Audio RMS→aa blendshape
- [ ] Idle animations: breathing, blinking, sway
- [ ] Audio player: PCM decode, queue, duck (<200ms)
- [ ] WebSocket client: reconnect z backoff, event dispatch
- [ ] Config Panel: 7 tabs, debounced save
- [ ] Setup Wizard: 6 steps
- [ ] Global hotkeys: Ctrl+Shift+A (toggle), Ctrl+Shift+S (settings)
- [ ] Click-through toggle (voice + UI)
- [ ] Drag & drop positioning, save position
- [ ] Text overlay (silent mode)
- [ ] `emotions.json` loaded at startup

### B) Testy

- [ ] Testy EMO-01→07 (frontend unit)
- [ ] WebSocket reconnect test (kill→reconnect→state sync)
- [ ] VRM loading test (capabilities scan correct)

### C) Performance

- [ ] Frontend GPU <2%, memory <300MB
- [ ] Avatar 60fps (visible), 30fps (minimized)
- [ ] Startup <5s (Electron launch→avatar visible)

### D) Acceptance Demos

- [ ] Demo 1: Full pipeline: PTT→response→avatar animacja+głos
- [ ] Demo 2: Observer: awatar komentuje grę z emocją
- [ ] Demo 3: 16 emocji: trigger każdą, weryfikuj wizualizację
- [ ] Demo 4: Lip-sync: TTS audio → usta się ruszają
- [ ] Demo 5: Config Panel: zmiana persona, interwał, volume — live
- [ ] Demo 6: Setup Wizard od zera na czystym systemie

### E) Pre-release Checklist

- [ ] Backup/restore tested
- [ ] Crash recovery tested (kill -9 → restart → resume)
- [ ] Sandbox audit: wszystkie ścieżki w whitelist
- [ ] Performance baseline documented
- [ ] LICENSES.md complete (VRM attributions)
- [ ] README.md complete
- [ ] CHANGELOG.md up to date

---

*Dokument: DOK-14 DEFINITION_OF_DONE.md v1.0 — 2026-05-02*
