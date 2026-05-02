# DOK-13: TEST_PLAN.md — Strategia Testów

> **Status:** v1.0 — 2026-05-02
> **Materiały źródłowe:** PRD_06_IMPLEMENTATION.md, ALGORITHMS_SPEC.md (test cases), COMMANDS_SPEC.md, MCP_TOOLS_SPEC.md, EMOTION_SPEC.md, OBSERVER_SPEC.md

---

## 1. Piramida Testów

| Warstwa | Narzędzie | Cel | Coverage target |
|---------|-----------|-----|-----------------|
| **Unit** | pytest + pytest-asyncio | Izolowane klasy, pure logic | ≥80% |
| **Integration** | pytest + httpx TestClient | API, DB, pipeline | ≥60% |
| **Smoke** | Manual + skrypty | Full end-to-end | Kluczowe ścieżki |
| **Performance** | Custom benchmarks | FPS, latency, VRAM | Budżety z PRD_03 |

---

## 2. Mock Strategy

| Komponent | Mock w unit/integration | Realne w smoke |
|-----------|------------------------|----------------|
| LM Studio | `MockLLMClient` (canned responses) | ✅ Wymagany |
| Faster-Whisper | `MockSTT` (return text) | ✅ Z plikiem WAV |
| Piper TTS | `MockTTS` (return silence WAV) | ✅ Generuje audio |
| DXcam | `MockCapture` (static frame np.ndarray) | ✅ Real screen |
| Moondream2 | `MockVLM` (return description) | ✅ Real model |
| EasyOCR | `MockOCR` (return text) | ✅ Real model |
| ChromaDB | `EphemeralClient` | `EphemeralClient` |
| SQLite | `:memory:` | `:memory:` |
| DuckDuckGo | `MockDDGS` (canned results) | ✅ (jeśli online) |
| Web scraper | `MockScraper` (static HTML) | ✅ (jeśli online) |

### 2.1 Fixture bazowy (`conftest.py`)

```python
@pytest.fixture
async def in_memory_db():
    async with aiosqlite.connect(":memory:") as db:
        db.row_factory = aiosqlite.Row
        await MigrationRunner().up(db)
        yield db

@pytest.fixture
def ephemeral_chroma():
    client = chromadb.EphemeralClient()
    yield {
        "conversations": client.create_collection("conversations"),
        "knowledge_base": client.create_collection("knowledge_base"),
    }

@pytest.fixture
def mock_config():
    return AppConfig()  # all defaults

@pytest.fixture
def mock_llm():
    return MockLLMClient(default_response="[EMO:amused] Test odpowiedź.")
```

---

## 3. Test Cases — Index z dokumentacji

### 3.1 GPU Scheduler (DOK-08 §1.4)

| ID | Scenariusz | Oczekiwane |
|----|-----------|------------|
| GPU-T-01 | STT + VLM jednocześnie | STT pierwsze (P1 < P4) |
| GPU-T-02 | 5 LLM requestów | FIFO per priorytet |
| GPU-T-03 | Task > 60s | `GPUTimeoutError` |
| GPU-T-04 | Task w kolejce 35s | Priority bump o 1 |

### 3.2 Circuit Breaker (DOK-08 §2.5)

| ID | Scenariusz | Oczekiwane |
|----|-----------|------------|
| CB-T-01 | 3 failures | State → OPEN |
| CB-T-02 | State OPEN, request | `CircuitOpenError` |
| CB-T-03 | State OPEN, 30s elapsed | State → HALF_OPEN |
| CB-T-04 | HALF_OPEN + success | State → CLOSED |
| CB-T-05 | HALF_OPEN + failure | State → OPEN |
| CB-T-06 | HTTP 404 response | Failures count nie rośnie |

### 3.3 Session Watchdog (DOK-08 §3.4)

| ID | Scenariusz | Oczekiwane |
|----|-----------|------------|
| WD-T-01 | Brak ticku 35s | `_handle_hibernation()` |
| WD-T-02 | Normalny tick 5s | Brak akcji |
| WD-T-03 | Startup z unclosed session | Marked `crashed` |
| WD-T-04 | Hibernate + LM Studio offline | Emocja `sad` |

### 3.4 Rate Limiter (DOK-08 §4.3)

| ID | Scenariusz | Oczekiwane |
|----|-----------|------------|
| RL-T-01 | 10 calls w 1s | 10 sukcesów (burst) |
| RL-T-02 | 11. call w 1s | `RateLimitedError` |
| RL-T-03 | 10 calls, 60s, 10 calls | 20 sukcesów |

### 3.5 MCP Cache (DOK-08 §5.5)

| ID | Scenariusz | Oczekiwane |
|----|-----------|------------|
| CACHE-T-01 | Powtórzony query < TTL | Cache hit |
| CACHE-T-02 | Invalidate + re-query | Fresh fetch |
| CACHE-T-03 | 2 parallel identical | Lock: 2. czeka na 1. |
| CACHE-T-04 | Entry > TTL | Treated as miss |

### 3.6 Observer Loop (DOK-08 §6.2)

| ID | Scenariusz | Oczekiwane |
|----|-----------|------------|
| OBS-T-01 | PTT aktywny | Skip cycle |
| OBS-T-02 | Identyczny hash × 3 | Skip cycle |
| OBS-T-03 | VLM timeout 11s | Skip (nie crash) |
| OBS-T-04 | LLM zwraca "[SKIP]" | Brak TTS |

### 3.7 Command Matcher (DOK-07 §13)

| ID | Input | Expected |
|----|-------|----------|
| CMD-T-01 | "idź spać" | CMD-01 sleep |
| CMD-T-02 | "id spac" | CMD-01 (fuzzy) |
| CMD-T-03 | "śpij teraz proszę" | CMD-01 |
| CMD-T-04 | "nie idź spać" | Brak (negacja) |
| CMD-T-05 | "ustaw interwał na 15 sekund" | CMD-11 {n:15} |
| CMD-T-06 | "ustaw interval na 15 sekund" | CMD-11 (fuzzy) |
| CMD-T-07 | "zmień personę na komentator" | CMD-12 |
| CMD-T-08 | "gram teraz TankMasterem" | CMD-13 |
| CMD-T-09 | "czy jest pora na spanie?" | → LLM |
| CMD-T-10 | "zacznij obserwowac i zmien persone na komentator" | CMD-03 + CMD-12 |
| CMD-T-11 | "zrob backup" | CMD-07 (fuzzy) |

### 3.8 MCP Tools (DOK-10 §F)

| ID | Tool | Scenariusz | Oczekiwane |
|----|------|-----------|------------|
| MCP-T-01 | web_search | Query "PoE2 LA build" | 5 wyników |
| MCP-T-02 | web_search | Identical < 24h | Cache hit |
| MCP-T-03 | web_search | 11. call/min | `RateLimitedError` |
| MCP-T-04 | web_search | offline=false | `OfflineModeError` |
| MCP-T-05 | web_scraper | Static HTML | Treść extracted |
| MCP-T-06 | web_scraper | SPA (pusta treść) | Playwright fallback |
| MCP-T-07 | get_current_time | Call | iso, weekday_pl |
| MCP-T-08 | calculator | "(450+78)*1.35" | 713.16 |
| MCP-T-09 | calculator | "import os" | NameError |
| MCP-T-10 | generate_document | format=html | Plik w documents/ |
| MCP-T-11 | generate_document | Same hint 2× | Unique timestamps |
| MCP-T-12 | screen_capture | focus_cursor=true | description+ocr |
| MCP-T-13 | sandbox | path="../../../etc" | `SandboxViolation` |

### 3.9 Emotion System (DOK-06 §12.2)

| ID | Input | Oczekiwane |
|----|-------|------------|
| EMO-01 | `[EMO:happy]` | blendshape=1.0, aura=#FFD700 |
| EMO-02 | `[EMO:unknown]` | Fallback neutral, WARNING |
| EMO-03 | Brak tagu | persona bias lub neutral |
| EMO-04 | scared podczas amused | Override (100 > 35) |
| EMO-05 | Model bez blendshapes | Aura+body only |
| EMO-06 | Audio chunk 50ms | lip-sync aa=RMS×4 |
| EMO-07 | System state=error | Force sad:0.5 |

---

## 4. Performance Acceptance Criteria

| Metryka | Target | Pomiar |
|---------|--------|--------|
| FPS impact | <5% | PoE2/Stellaris z/bez |
| PTT→first audio | <3s | Timestamp diff |
| Observer cycle | <5s | Capture→comment |
| STT latency | <1s | Audio→text |
| VLM latency | <5s | Frame→description |
| VRAM peak | <30GB | nvidia-smi |
| Frontend FPS | 60fps visible, 30fps minimized | Three.js stats |
| Frontend memory | <300MB renderer | Chrome DevTools |

---

## 5. CI / Lokalne uruchamianie

```powershell
# Unit + Integration testy
cd c:\code\_repos\antigravity\assystent
.\.venv\Scripts\Activate.ps1
pytest tests/ -v --tb=short --asyncio-mode=auto

# Tylko unit (bez AI models)
pytest tests/unit/ -v -m "not slow"

# Coverage
pytest tests/ --cov=backend --cov-report=html

# Performance baseline
python scripts/benchmark.py --game poe2 --duration 300
```

---

## 6. Struktura katalogów testów

```
tests/
├── conftest.py           # shared fixtures, mocks
├── unit/
│   ├── test_config.py
│   ├── test_gpu_scheduler.py
│   ├── test_circuit_breaker.py
│   ├── test_rate_limiter.py
│   ├── test_command_matcher.py
│   ├── test_emotion_parser.py
│   ├── test_prompt_builder.py
│   ├── test_sandbox.py
│   └── test_cache.py
├── integration/
│   ├── test_api_health.py
│   ├── test_api_config.py
│   ├── test_api_voice.py
│   ├── test_websocket.py
│   ├── test_session_repo.py
│   ├── test_message_repo.py
│   ├── test_mcp_tools.py
│   └── test_observer.py
├── smoke/
│   ├── test_full_pipeline.py
│   └── test_startup.py
└── performance/
    ├── test_fps_impact.py
    └── test_latency.py
```

---

*Dokument: DOK-13 TEST_PLAN.md v1.0 — 2026-05-02*
