# DOK-14: DEFINITION_OF_DONE.md — Kryteria Akceptacji per Faza

> **Status:** v1.2 — 2026-05-09 (link do STAN_IMPLEMENTACJI)
> **Bieżąca tabela wdrożenia:** [STAN_IMPLEMENTACJI.md](STAN_IMPLEMENTACJI.md)
> **Materiały źródłowe:** PRD_06_IMPLEMENTATION.md, TEST_PLAN.md
>
> **Legenda:** `[x]` spełnione w kodzie · `[~]` częściowe / wymaga pomiaru lub ręcznego demo · `[ ]` brak / ponad MVP

---

## Faza 1 — Backend Core (MVP-1)

### A) Code Complete

- [x] FastAPI app startuje (`uvicorn backend.main:app`)
- [x] Config loader: defaults → YAML → env (`ASSY_`), walidacja Pydantic; `PUT /api/v1/config` zapisuje zwalidowany `model_dump` do YAML
- [x] Interfejsy bazowe: `BaseLLMClient`, `BaseSTTEngine`, `BaseTTSEngine`, `BaseVLMAnalyzer`
- [x] `GPUScheduler` — kolejka priorytetów (STT/LLM/TTS/VLM)
- [x] `CircuitBreaker` — stany i integracja z LLM
- [x] `LMStudioClient` — streaming SSE, function calling, circuit breaker
- [x] `FasterWhisperSTT` — progi pewności, GPU scheduler
- [x] `PiperTTS` — subprocess (w tym `asyncio.to_thread` na Windows), modulacja emocji (`tts_emotion.py`)
- [x] `WakewordDetector` — openWakeWord, degradacja bez pakietu
- [x] Wejście audio PTT — `PTTHotkeyListener` (pynput, opcjonalnie) + `VoiceInputCoordinator`; **nie** osobna klasa `AudioCapture` (nagrywanie WAV przez frontend)
- [x] `ConversationOrchestrator` — komendy → LLM → narzędzia → TTS / stany wizualne
- [x] `PromptBuilder`, `parse_emotion_tag`, `CommandMatcher` (regex + fuzzy dla CMD-01)
- [x] **22** wbudowane reguły komend (`CMD-01` … `CMD-22` w `command_matching.py`), nie 16
- [x] `SessionWatchdog`, recovery sesji, integracja z health
- [x] REST: `/health`, `/status` (agregacja `build_health_snapshot`), `/config`, endpointy voice i player-profile wg `routes.py`
- [x] WebSocket: multi-event (`emotion`, `audio_stream`, `visual_state`, `audio_duck`, itd.)
- [x] MCP: m.in. `get_current_time`, `calculator` + rejestr rozszerzalny
- [x] SQLite: migracje `001_initial.sql` + `002_*`, runner, tabele domenowe + `schema_migrations` (12 tabel biznesowych + migracje; `002` relaksuje `tool_calls`)
- [x] Hot-reload: `watchdog` na config i persony
- [ ] Warstwa `StorageBackend` / `SQLiteBackend` — **świadomie pominięta**; dostęp przez repozytoria

### B) Testy

- [~] ≥80% pokrycia `backend/core` — **nie utrzymywany automatyczny próg w CI**; wymaga `pytest --cov` do weryfikacji
- [~] Testy GPU-T / CB-T / WD-T / CMD-T — część w repo; pełna zgodność z listą TEST_PLAN nie jest tu potwierdzona liczbowo
- [x] Zestaw testów integracyjnych API/WS (`tests/integration/`)
- [~] `pytest tests/` — utrzymywane w dev; brak gwarancji „zero fail” poza lokalnym/CI bez sprawdzenia

### C) Performance

- [ ] FPS wpływ < 5% (gra z vs bez asystenta) — **pomiar manualny / niedokumentowany**
- [ ] PTT → pierwsze audio < 3 s — **end-to-end zależny od frontendu; nie zmierzone formalnie**
- [ ] Opóźnienia udokumentowane w raporcie wydajności

### D) Acceptance Demos (manual)

- [~] Demo 1–4: ścieżki istnieją; **wymagają potwierdzenia na środowisku użytkownika**
- [~] Demo 5: reload konfiguracji — hot-reload jest; dokładna fraza głosowa zależy od handlera / TTS
- [x] Demo 6: recovery po crashu — logika `recover_stale_sessions` + testy recovery

---

## Faza 2 — Vision, MCP, Memory (MVP-2)

### A) Code Complete

- [x] Zrzut ekranu: DXcam → mss → pyautogui (`DesktopScreenCapture`), wybór monitora przez indeks
- [x] `Moondream2VLM` (opcjonalnie), kolejka GPU P4
- [x] EasyOCR opcjonalnie (`requirements-vision.txt`), dual pipeline z VLM
- [x] `GameObserver` / wykrywanie gry (proces + VLM fallback + profil ręczny)
- [x] Profile gier + hot-reload
- [x] `ObserverLoop`, SceneDeduper (dHash), współdziałanie z PTT
- [~] Ograniczenie tempa komentarzy / różnorodność — częściowo (kolejki, dedupe); „cosine” jak w starej spec może się różnić
- [x] `web_search`, `web_scraper`, `generate_document`, `screen_capture`, sandbox, cache MCP
- [x] Chroma: dwie kolekcje semantyczne; `SemanticRecall`, `KnowledgeIngester`; FIFO przez `prune_*` / limity konfiguracyjne
- [x] `PlayerProfileRepository`, daily meta, league hint, archiwum profilu (REST + WS)
- [~] Backup ZIP / logi .7z / „season reset” — sprawdź `command_handlers` / MCP; nie wszystkie zdania DoD v1.0 są 1:1 z kodem
- [x] Tryb online / rate limiting MCP — zgodnie z konfiguracją

**Uwaga:** W **DECISIONS_LOG** zapisano `pygetwindow` dla monitora gry — **w backendzie nie używamy** tej biblioteki; działa `monitor_index` + lista monitorów (Electron: wybór wyświetlacza overlaya).

### B) Testy

- [~] OBS / RL / CACHE / MCP — testy jednostkowe i integracyjne istnieją; pełna mapa ID z TEST_PLAN nieverifikowana tu

### C) Acceptance Demos

- [~] Demo 1–6 — możliwe przy skonfigurowanym LM Studio, grze i MCP; status **manual**

---

## Faza 3 — Frontend + Avatar (Release)

### A) Code Complete

- [x] Electron: overlay przezroczysty, tray, osobne okno konfiguracji, IPC
- [x] React: awatar (`AvatarCanvas`), Config Panel (w tym zakładka Status, Obserwator, Persona, itd.), Setup Wizard
- [x] Three.js + VRM, crossfade emocji, AuraLights, idle (mruganie, kołysanie), spring bones (aktualizacja po animacji ciała)
- [x] Mapowanie emocji z `emotions.json` (17 stanów / palety w aurze)
- [x] Lip-sync (RMS → blendshape), odtwarzacz PCM, duck przy PTT
- [x] WebSocket: reconnect z backoff, zdarzenia (w tym `visual_state`, profil gracza)
- [x] Panel konfiguracji: wiele zakładek, debounced PUT, token do `PUT /config`
- [x] Kreator startowy (`SetupWizard.tsx`)
- [~] Globalne hotkeys — sprawdź `electron-main.cjs` / skróty z dokumentacji; mogą się różnić od Ctrl+Shift+A/S z pierwotnego DoD
- [x] Click-through (komenda + UI), text overlay (tryb cichy)
- [x] Pozycja / rozmiar okna (persist typowego stanu — weryfikacja w kodzie Electron)
- [ ] Dedykowana sekcja **Credits** z atrybucją VRM w panelu — **DECISIONS_LOG** wymaga; w UI może być tylko pośrednio (README / `LICENSES.md`)

### B) Testy

- [~] Testy emocji / frontend — część logiki w `emotionBlend.ts`; pełna lista EMO-01→07 niepotwierdzona
- [ ] Automatyczny test reconnect WebSocket — opcjonalny
- [~] Ładowanie VRM — ręczne / środowiskowe

### C) Performance

- [ ] Budżety FPS / RAM / startup z DoD v1.0 — **nieweryfikowane formalnie**

### D) Acceptance Demos

- [~] Demo 1–6 — zależne od sprzętu; wizard i pełny pipeline dostępne w buildzie

### E) Pre-release Checklist

- [~] Backup / crash recovery — logika backendu + testy częściowe; pełny runbook użytkownika w `docs/`
- [x] Sandbox audit — testy `tests/unit/test_sandbox_audit.py` (CHANGELOG)
- [ ] Performance baseline — dokument opisowy / benchmarki
- [~] `LICENSES.md` — istnieje; **placeholder atrybucji modelu VRM** do uzupełnienia (CHANGELOG)
- [x] README z linkami do poradnika użytkownika
- [~] `CHANGELOG.md` — sekcja `[Unreleased]` bogata; przed wydaniem — podbić wersję i datę

---

*Dokument: DOK-14 DEFINITION_OF_DONE.md v1.2 — 2026-05-09*
