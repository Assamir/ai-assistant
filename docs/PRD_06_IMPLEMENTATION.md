# PRD 06: Implementacja i Testy

> Część 6/6 — [Powrót do indeksu](PRD_00_INDEX.md)

---

## 1. Fazy Realizacji

### Faza 1 — Backend Core (MVP-1)

**Cel:** Działający pipeline głosowy: PTT → STT → LLM → TTS → audio.  
**Szacowany czas:** 3-4 tygodnie (solo-dev)

- [ ] Inicjalizacja projektu Python + FastAPI + środowisko wirtualne
- [ ] Struktura katalogów content root (`c:\ai\asystent`)
- [ ] Config loader (`config.yaml`) z walidacją
- [ ] Interfejsy bazowe (`BaseLLMClient`, `BaseSTTEngine`, `BaseTTSEngine`, `BaseVLMAnalyzer`, `StorageBackend`)
- [ ] Klient LM Studio (OpenAI-compatible API + function calling)
- [ ] Circuit breaker dla połączenia z LM Studio
- [ ] Moduł STT (Faster-Whisper) z confidence threshold
- [ ] Moduł TTS (Piper) z modulacją emocji (speed/pitch)
- [ ] Moduł wakeword (openWakeWord)
- [ ] Zarządzanie trybami nagrywania (PTT via pynput + wakeword)
- [ ] Orkiestrator AI (prompt builder, emotion parser, command matcher)
- [ ] GPU Scheduler (mutex/semaphore)
- [ ] Session Watchdog (hibernation recovery)
- [ ] Komendy systemowe (commands.yaml + regex matcher)
- [ ] System persona (ładowanie plików .md)
- [ ] WebSocket + REST API dla frontendu
- [ ] MCP: `get_current_time`, `calculator`
- [ ] Logowanie: session transcripts, system status
- [ ] **Performance Baseline Test** (z grą vs bez)
- [ ] Unit testy z mockami

**Kamień milowy:** Użytkownik rozmawia z asystentem głosowo z terminala. Emocje zwracane jako tagi. Komendy systemowe działają.

---

### Faza 2 — Wizja, MCP i Pamięć (MVP-2)

**Cel:** Asystent widzi ekran, szuka w internecie, pamięta kontekst.  
**Szacowany czas:** 3-4 tygodnie

- [ ] Integracja DXcam z benchmarkiem wydajności
- [ ] Moduł VLM (Moondream2) z GPU Scheduler
- [ ] Moduł OCR (EasyOCR) — pipeline dual (VLM + OCR)
- [ ] Game detector (kaskadowy: proces → VLM → ręczne)
- [ ] Game profiles (YAML loader + hot-reload)
- [ ] Observer loop (game observer + interwał konfigurowalny)
- [ ] On-demand screen query (capture + cursor position + crop)
- [ ] Logika priorytetów (user interaction > observer)
- [ ] MCP: `web_search` (DuckDuckGo) z rate limiter + cache
- [ ] MCP: `web_scraper` z cache
- [ ] MCP: `generate_document` (MD + HTML z Mermaid)
- [ ] MCP: `screen_capture` (on-demand)
- [ ] SQLite backend (historia konwersacji, Repository Pattern)
- [ ] ChromaDB/LanceDB (pamięć semantyczna)
- [ ] Player profile (YAML, multi-character)
- [ ] Daily meta check (on startup, low priority)
- [ ] Season reset detection
- [ ] Knowledge base (folder `knowledge/`)
- [ ] Auto-archiwizacja logów (.7z)
- [ ] Backup/restore (zip content root)
- [ ] File watcher (hot-reload config, personas)
- [ ] Granularne priorytety wątków
- [ ] Unit + integration testy

**Kamień milowy:** Asystent komentuje PoE2/Stellaris, szuka buildów online, pamięta profil gracza, generuje raporty.

---

### Faza 3 — Frontend i Awatar 3D (Release)

**Cel:** Pełna aplikacja desktopowa z awatarem 3D i emocjami.  
**Szacowany czas:** 4-6 tygodni

- [ ] Electron + React setup (frameless, transparent, Always-on-Top)
- [ ] Three.js + three-vrm renderer
- [ ] Domyślny model VRM (stylizowany anime, CC license)
- [ ] 16 emocji: blendshape mapping + skan przy ładowaniu modelu
- [ ] Proceduralnie animacje per emocja (Three.js, VRMHumanoid)
- [ ] Aura/shader per emocja (fallback layer)
- [ ] Stany wizualne systemu (listening, thinking, speaking, error, degraded)
- [ ] Lip-sync na podstawie audio stream (WebSocket)
- [ ] Animacje idle (mruganie, oddychanie, kołysanie)
- [ ] Panel konfiguracji (mikrofon, głośniki, VRM, persona, tryby)
- [ ] Zakładka Status (VRAM, wątki, stan obserwatora)
- [ ] System tray (Start/Stop/Restart/Settings/Quit)
- [ ] Globalny hotkey `Ctrl+Shift+A`
- [ ] Text overlay (tryb cichy)
- [ ] Audio duck (<200ms)
- [ ] Notification sound przed komentarzem
- [ ] Drag & drop pozycjonowanie awatara
- [ ] Skalowanie i przezroczystość
- [ ] WebSocket reconnect z heartbeat + state sync
- [ ] Setup wizard (first-run)
- [ ] Debug overlay (opcjonalny)
- [ ] Skrót na pulpicie

**Kamień milowy:** Kompletna aplikacja z awatarem 3D, gotowa do codziennego użytku.

---

## 2. Strategia Testowania

### 2.1 Zasady

| Zasada | Opis |
|--------|------|
| **Mocks dla AI** | Testy standardowe **bez** realnego LLM, STT, TTS, web |
| **Minimalne testy integracyjne** | 1-2 testy z realnym LLM Studio, oznaczone `@pytest.mark.slow` |
| **Szybkość** | Pełna suite (bez slow) < 30 sekund |
| **Coverage** | 80%+ logiki backendu |

### 2.2 Mocki

```python
class MockLLMClient(BaseLLMClient):
    """Zwraca predefiniowane odpowiedzi z tagami emocji."""
    async def chat(self, messages, tools=None):
        return Response(content="[EMO:happy] Mock response", tool_calls=[])

class MockSTTEngine(BaseSTTEngine):
    """Zwraca predefiniowany tekst z zadanym confidence."""
    async def transcribe(self, audio_data):
        return TranscriptionResult(text="test query", confidence=0.95)

class MockTTSEngine(BaseTTSEngine):
    """Zwraca ciszę (zerowe bajty audio)."""
    async def synthesize(self, text, emotion=None):
        return AudioData(samples=b'\x00' * 1024, sample_rate=22050)

class MockVLMAnalyzer(BaseVLMAnalyzer):
    """Zwraca predefiniowany opis sceny."""
    async def analyze(self, image, prompt):
        return "Player in inventory screen, looking at a rare bow"

class MockMCPWebSearch:
    """Zwraca predefiniowane wyniki wyszukiwania."""
    async def search(self, query):
        return [{"title": "Mock result", "url": "...", "snippet": "..."}]
```

### 2.3 Poziomy Testów

#### Unit Testy (pytest)

| Moduł | Co testujemy |
|-------|-------------|
| `emotion_parser` | Parsowanie `[EMO:tag]` z odpowiedzi, usuwanie tagów |
| `command_matcher` | Regex matching komend systemowych, parametryzowane komendy |
| `prompt_builder` | Dynamiczne składanie promptu z komponentów |
| `circuit_breaker` | Przejścia stanów CLOSED → OPEN → HALF_OPEN → CLOSED |
| `gpu_scheduler` | Kolejkowanie z priorytetami, mutex |
| `config_loader` | Parsowanie YAML, walidacja, wartości domyślne |
| `player_profile` | CRUD postaci, zmiana aktywnej, archiwizacja |
| `game_detector` | Rozpoznawanie procesu, mapowanie na profil |
| `session_watchdog` | Wykrywanie hibernacji (mock czasu) |
| `mcp_cache` | TTL, bypass, cleanup |
| `document_generator` | MD → HTML konwersja, template injection |
| `sandbox_validator` | Whitelist ścieżek, blokowanie niedozwolonych |
| `rate_limiter` | Limity req/min, backoff |
| `stt_confidence` | Klasyfikacja confidence → akcja |

#### Integration Test (z mockami AI)

```python
@pytest.mark.integration
async def test_full_pipeline_with_mocks():
    """End-to-end test: fake audio → STT mock → LLM mock → TTS mock."""
    orchestrator = Orchestrator(
        llm=MockLLMClient(),
        stt=MockSTTEngine(),
        tts=MockTTSEngine(),
        vlm=MockVLMAnalyzer(),
    )
    result = await orchestrator.process_voice_input(fake_audio_data)
    assert result.emotion == "happy"
    assert result.audio_data is not None
    assert "[EMO:" not in result.text  # tag usunięty
```

#### Smoke Test (z realnym LLM)

```python
@pytest.mark.slow
@pytest.mark.skipif(not lm_studio_available(), reason="LM Studio not running")
async def test_real_llm_connection():
    """Minimalny test: ping LM Studio, wyślij prosty prompt."""
    client = LMStudioClient(url="http://localhost:1234/v1")
    response = await client.chat([{"role": "user", "content": "Powiedz 'ok'"}])
    assert "ok" in response.content.lower()
```

### 2.4 Performance Test

```python
@pytest.mark.slow
async def test_performance_baseline():
    """Loguj FPS/CPU/GPU z i bez asystenta."""
    # 1. Uruchom grę (manual) → loguj metryki 60s
    # 2. Uruchom asystenta → loguj metryki 60s
    # 3. Porównaj: delta FPS < 5%
    pass  # Semi-manual, wyniki w logs/
```

---

## 3. Ryzyka i Mitigacje

| # | Ryzyko | P-stwo | Wpływ | Mitigacja |
|---|--------|--------|-------|-----------|
| R1 | VRAM: VLM + LLM + TTS + gra przekraczają 32 GB | Średnie | Wysoki | Domyślne lekkie modele (Piper+Moondream2); sekwencyjne inference (GPU Scheduler); VRAM budget monitoring |
| R2 | Latency end-to-end > 3s | Średnie | Średni | Streaming odpowiedzi; sub-metryki per komponent; cache promptów; baseline test |
| R3 | DXcam niekompatybilny z grami (anty-cheat, fullscreen) | Średnie | Średni | Fallback metody capture; dokumentacja trybów; borderless jako wymaganie |
| R4 | STT jakość dla polskiego w hałasie | Niskie | Średni | Confidence threshold; noise suppression; Whisper model dobór |
| R5 | Konflikty hotkeys z grami | Niskie | Niski | Konfigurowalność klawiszy; wykrywanie kolizji |
| R6 | VLM nie rozpoznaje drobnego tekstu UI (itemy) | Średnie | Średni | Dual pipeline VLM + OCR; crop regionu |
| R7 | LLM hallucynuje o meta/buildach | Średnie | Średni | MCP web search; local knowledge base; instrukcja „szukaj jeśli nie wiesz" |
| R8 | Modele VRM z brakującymi blendshapes | Niskie | Niski | Trójwarstwowy fallback (blendshapes → aura → body) |
| R9 | Rate limiting DuckDuckGo | Niskie | Niski | Rate limiter; cache TTL 24h; SearXNG self-hosted jako opcja |
| R10 | Complexity creep (solo-dev, duży scope) | Wysokie | Wysoki | Ścisłe trzymanie się faz; MVP-first; testy po każdej fazie |

---

## 4. Definition of Done — MVP

### Faza 1 (MVP-1) ✓

- [ ] Pipeline głosowy działa: PTT → STT → LLM → TTS → audio
- [ ] Wakeword działa jako alternatywa dla PTT
- [ ] Komendy systemowe wykonują się bez LLM
- [ ] Circuit breaker obsługuje brak LM Studio
- [ ] Persona ładowana z pliku .md
- [ ] Emocje zwracane jako tagi (bez awatara)
- [ ] Testy unitowe: 80%+ coverage, <30s
- [ ] Performance baseline vs Stellaris/PoE2

### Faza 2 (MVP-2) ✓

- [ ] Obserwator komentuje PoE2 (action, 5s interwał)
- [ ] Obserwator komentuje Stellaris (strategic, 15s interwał)
- [ ] On-demand screen query działa
- [ ] MCP web search + scraper działają z cache
- [ ] Daily meta check wykonuje się przy starcie
- [ ] Profil gracza z wieloma postaciami
- [ ] Generowanie dokumentów MD/HTML
- [ ] Pamięć semantyczna (recall kontekstu)
- [ ] Auto-archiwizacja logów

### Faza 3 (Release) ✓

- [ ] Awatar 3D wyświetla się jako overlay
- [ ] 16 emocji z unikalnymi animacjami
- [ ] Lip-sync zsynchronizowany z mową
- [ ] Panel konfiguracji funkcjonalny
- [ ] System tray + globalny hotkey
- [ ] Setup wizard dla first-run
- [ ] Tryb cichy (text overlay)
- [ ] Audio duck przy PTT
- [ ] Całość działa offline (MCP degraduje gracefully)
- [ ] Wpływ na FPS < 5%

---

## 5. Harmonogram Szacunkowy

```
Faza 1 (Backend Core):     Tygodnie 1-4
  ├── Setup + Interfaces:   Tydzień 1
  ├── STT + TTS + LLM:      Tydzień 2
  ├── Orkiestrator + Komendy: Tydzień 3
  └── Testy + Baseline:     Tydzień 4

Faza 2 (Wizja + MCP):      Tygodnie 5-8
  ├── DXcam + VLM + OCR:    Tydzień 5
  ├── Observer + Game Profiles: Tydzień 6
  ├── MCP Tools + Cache:     Tydzień 7
  └── Pamięć + Dokumenty:   Tydzień 8

Faza 3 (Frontend):         Tygodnie 9-14
  ├── Electron + Three.js:   Tydzień 9-10
  ├── Emocje + Animacje:     Tydzień 11-12
  ├── UI + Konfiguracja:     Tydzień 13
  └── Polish + Setup Wizard: Tydzień 14

TOTAL: ~14 tygodni (~3.5 miesiąca)
```

> [!NOTE]
> Harmonogram zakłada pełnoetatową pracę jednej osoby. Przy pracy part-time odpowiednio pomnóż.

---

*Koniec dokumentacji PRD. [Powrót do indeksu](PRD_00_INDEX.md)*
