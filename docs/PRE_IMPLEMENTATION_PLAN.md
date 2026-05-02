# Plan Przygotowania Dokumentacji przed Implementacją — Assystent

> **Cel:** Uzupełnić lukę między PRD/DB_SCHEMA a kodem. Po wykonaniu tego planu programista (lub LLM coding agent) powinien móc rozpocząć Fazę 1 bez dodatkowych pytań projektowych.
>
> **Status wejściowy:** Mamy PRD (6 części), DB_SCHEMA, PROJECT_PLAN, **DECISIONS_LOG.md**.
> **Brakuje:** kontraktów API, formatów konfiguracji, algorytmów krytycznych, definicji testów akceptacyjnych, środowiska deweloperskiego.
>
> **Zasada:** Każdy dokument powstaje **w osobnej sesji/wątku z LLM** (czysty kontekst), z dołączonym właściwym PRD jako materiałem źródłowym. Po każdym dokumencie — przegląd przez użytkownika i ewentualna korekta przed przejściem do następnego.

---

## ⚠️ WAŻNE: Załączaj DECISIONS_LOG.md do KAŻDEGO promptu

Plik `DECISIONS_LOG.md` zawiera odpowiedzi na **wszystkie** pytania projektowe zadane podczas tworzenia tego planu (sekcje "Pytania do użytkownika" w DOK-02, DOK-03, DOK-05, DOK-07, DOK-09, DOK-10, DOK-12). Załączaj go zawsze obok PRD i innych materiałów źródłowych.

**Pominięcie tego pliku = ryzyko niespójności z podjętymi decyzjami.**

Sekcje "Pytania do użytkownika" w poniższych promptach pozostawiono jako historyczny ślad. Odpowiedzi są w `DECISIONS_LOG.md`. **Nie pytaj o nie ponownie** — używaj wartości z logu.

---

## Mapa Zależności

```
                    ┌─────────────────────────┐
                    │ PRD (01-06) + DB_SCHEMA │  (input)
                    └────────────┬────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
   01 GLOSSARY              02 ENV_SETUP            03 CONFIG_SPEC
   (terminologia)          (zależności,           (config.yaml,
                            modele do pobrania)    walidacja, schema)
        │                        │                        │
        └────────────────────────┼────────────────────────┘
                                 ▼
                    04 API_CONTRACT (REST + WebSocket)
                                 │
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
   05 PROMPT_SPEC          06 EMOTION_SPEC         07 COMMANDS_SPEC
   (system prompts,        (16 emocji, mapping     (regex, parametry,
    function schemas,       blendshapes, TTS,       custom DSL)
    persona format)         animacje)
        │                        │                        │
        └────────────────────────┼────────────────────────┘
                                 ▼
                    08 ALGORITHMS_SPEC
              (GPU scheduler, circuit breaker,
               session watchdog, rate limiter,
               cache, observer loop)
                                 │
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
   09 OBSERVER_SPEC        10 MCP_TOOLS_SPEC      11 MEMORY_SPEC
   (game profiles,         (6 tools — input/      (recall, ingestion,
    VLM+OCR pipeline,       output schema,          rotation, archiving,
    detekcja, on-demand)    sandbox, errors)        player profile)
        │                        │                        │
        └────────────────────────┼────────────────────────┘
                                 ▼
                    12 FRONTEND_SPEC
              (Electron config, VRM loading,
               WebSocket client, lip-sync,
               panel konfiguracji)
                                 │
                                 ▼
                       13 TEST_PLAN
                  (unit, integration, smoke,
                   performance, mocki, coverage)
                                 │
                                 ▼
                    14 DEFINITION_OF_DONE
              (checklisty per faza, kryteria
               akceptacji, kamienie milowe)
                                 │
                                 ▼
                    15 RISK_REGISTER
              (rozszerzenie ryzyk z PRD,
               playbooks reakcji)
                                 │
                                 ▼
                    16 IMPLEMENTATION_ROADMAP
              (zadania per dzień/tydzień,
               kolejność, dependencies)
```

---

## Konwencje Promptów

Każdy prompt zaczyna się od bloku:

```
KONTEKST: Tworzysz dokument [NAZWA] dla projektu Assystent — lokalny asystent
gracza AI z awatarem 3D. Załączam:
- PRD (6 części) + DB_SCHEMA.md jako podstawę domenową
- DECISIONS_LOG.md — ZAWIERA WSZYSTKIE PODJĘTE DECYZJE PROJEKTOWE
- [poprzednie dokumenty DOK-XX z plan'u jako kontekst spójności]

KRYTYCZNE: DECISIONS_LOG.md jest source of truth dla decyzji.
Nie zadawaj pytań o rzeczy które są w nim zdecydowane.
Stosuj wartości z DECISIONS_LOG bez podważania.

ZASADY:
- Tylko polski (oprócz nazw technicznych, kodu, nazw plików)
- Markdown z tabelami, sekcjami numerowanymi, blokami kodu
- Konkretne wartości, nie ogólniki ("TTL 86400s" zamiast "długi TTL")
- Przykłady kodu w Python 3.10+ (typing, async/await)
- Każda decyzja uzasadniona w 1-2 zdaniach
- Sekcja "Pytania otwarte" na końcu TYLKO jeśli pojawiły się NOWE wątpliwości
  niepokryte w DECISIONS_LOG (nie powtarzaj odpowiedzianych)
- Sekcja "Reguły naczelne uwzględnione w tym dokumencie" — wymień które z
  10 reguł z DECISIONS_LOG są materialne dla tego dokumentu
```

---

# DOKUMENTY DO UTWORZENIA — KOLEJNOŚĆ

## DOK-01: GLOSSARY.md — Słownik Pojęć

**Po co:** Ujednolicenie terminologii. PRD używa miksu PL/EN ("observer", "wakeword", "scene", "build", "liga"). Bez słownika = niespójny kod i UI.

**Materiały źródłowe do dołączenia:**
- Wszystkie 6 plików PRD
- DB_SCHEMA.md

**Prompt:**

> Wygeneruj `GLOSSARY.md` — słownik pojęć projektu Assystent. Wyciągnij **wszystkie** terminy techniczne i domenowe z załączonej dokumentacji PRD i DB_SCHEMA.
>
> Struktura per termin:
> ```
> ### Termin (PL) / Term (EN)
> - **Definicja:** krótka, 1-2 zdania
> - **Użycie w kodzie:** np. `class GameDetector`, `enum Emotion.HAPPY`
> - **Użycie w UI:** jak wyświetlać użytkownikowi
> - **Synonimy do unikania:** np. "tryb obserwatora" ≠ "monitorowanie"
> ```
>
> Pogrupuj kategoriami:
> 1. Stany systemu (Healthy, Degraded, Minimal, Idle, Observer Active, Conversation Lock, Sleep)
> 2. Komponenty AI (LLM, STT, TTS, VLM, OCR, Wakeword)
> 3. Pamięć i persystencja (sesja, snapshot, profil gracza, persona)
> 4. Obserwator (game observer, on-demand query, ambient observer, scene_hash)
> 5. MCP Tools (function calling, tool call, turn sequence)
> 6. Awatar (VRM, blendshape, aura, emocja, stan wizualny)
> 7. Audio (PTT, wakeword, audio duck, tryb cichy, confidence)
> 8. Domena gier (build, liga, klasa, postać, meta, sezon)
>
> Na końcu: tabela "Mapowanie EN → PL dla UI" (np. "thinking" → "myślę…").

**Akceptacja:** Min. 60 terminów. Każdy ma użycie w kodzie i UI. Brak duplikatów/synonimów.

---

## DOK-02: ENV_SETUP.md — Środowisko Deweloperskie

**Po co:** Bez tego pierwszy dzień implementacji to walka z zależnościami. Dokument ma być uruchamialnym manualem.

**Materiały źródłowe:**
- PRD_03_NONFUNCTIONAL.md (sekcja Kompatybilność, VRAM Budget)
- PRD_04_ARCHITECTURE.md (Tech Stack)
- PRD_06_IMPLEMENTATION.md (Faza 1)

**Prompt:**

> Wygeneruj `ENV_SETUP.md` — kompletny manual setupu środowiska deweloperskiego dla projektu Assystent. Załączam PRD jako kontekst.
>
> Sekcje:
>
> 1. **Wymagania sprzętowe i systemowe** — minimum vs zalecane, weryfikacja CUDA, GPU
> 2. **Software prerequisites** — Python 3.10+, Node.js 18+, Git, LM Studio z linkami i wersjami
> 3. **Struktura katalogów** — tworzenie content root `c:\ai\asystent` ze wszystkimi podkatalogami z PRD_04
> 4. **Python environment** — `python -m venv`, aktywacja Windows, `requirements.txt` z konkretnymi wersjami (faster-whisper==X, openwakeword==X, dxcam==X, fastapi==X, chromadb==X, asteval==X, watchdog==X, py7zr==X, sentence-transformers==X, easyocr==X, pynput==X, psutil==X, sqlite-vec / chromadb)
> 5. **Pobieranie modeli AI** — komendy/skrypty do:
>    - Faster-Whisper medium (Hugging Face)
>    - Piper voice PL (link do głosu)
>    - openWakeWord (jaki model dla "Hej Asystent")
>    - Moondream2 (Hugging Face)
>    - EasyOCR (auto-download)
>    - sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
>    - Domyślny VRM (link do CC-BY model)
>    Z weryfikacją checksum gdzie możliwe i ścieżkami docelowymi w `c:\ai\asystent\models\`
> 6. **LM Studio setup** — pobranie Gemma 4 E4B (alternatywnie sugestie zastępcze), ustawienia function calling, port 1234, weryfikacja `curl http://localhost:1234/v1/models`
> 7. **Frontend setup** — `npm install`, struktura, electron-builder
> 8. **Pierwsze uruchomienie** — kolejność: LM Studio → backend → frontend; sanity check każdego komponentu osobno
> 9. **Troubleshooting** — najczęstsze problemy: CUDA out of memory, brak głosu Piper, mikrofon nie wykryty, port 1234 zajęty, antywirus blokuje DXcam
> 10. **Skrypty pomocnicze** — `scripts/setup.ps1`, `scripts/download_models.py`, `scripts/verify_env.py` (z opisem co robi każdy)
>
> Dla **każdej** zewnętrznej zależności podaj: rozmiar instalacji, VRAM/RAM wymagany, link oficjalny, alternatywę gdyby ta zniknęła.

**Akceptacja:** Osoba na świeżym Windows powinna móc skonfigurować projekt w <2h. Każdy krok ma weryfikację.

**Pytania do użytkownika przed promptem:**

> ❓ **Dla użytkownika przed wygenerowaniem DOK-02:**
> 1. Czy potwierdzasz Gemma 4 E4B jako domyślny LLM, czy są dostępne alternatywy które LM Studio popiera lokalnie (np. Llama 3.x, Qwen 2.5)?
> 2. Czy masz preferencję głosu Piper (męski/żeński, jaka jakość — `medium`, `high`)?
> 3. Czy wakeword "Hej Asystent" jest finalny, czy do zmiany? (wpływa na wybór modelu openWakeWord — predefiniowany vs custom training)
> 4. Czy domyślny model VRM ma być z konkretnego źródła (VRoid Hub, Booth), czy ma być prosty placeholder?

---

## DOK-03: CONFIG_SPEC.md — Specyfikacja Konfiguracji

**Po co:** PRD pokazuje przykład `config.yaml`, ale nie definiuje walidacji, defaultów, edge cases, ani jak zachować się przy błędnym configu.

**Materiały źródłowe:**
- PRD_04_ARCHITECTURE.md (sekcja Konfiguracja Główna)
- PRD_03_NONFUNCTIONAL.md (sekcja Hot-Reload)
- PRD_02_FUNCTIONAL.md (komendy systemowe — commands.yaml)

**Prompt:**

> Wygeneruj `CONFIG_SPEC.md` — pełną specyfikację wszystkich plików konfiguracyjnych projektu Assystent.
>
> Dla **każdego pliku**:
> 1. **Lokalizacja** w `c:\ai\asystent\config\`
> 2. **JSON Schema** (lub Pydantic model) — typy, ograniczenia, regex, range, enum
> 3. **Wartości domyślne** — co używamy gdy klucz nieobecny
> 4. **Wartości wymagane vs opcjonalne**
> 5. **Walidacja semantyczna** — np. `quiet_hours[0]` musi być wcześniejsze niż `[1]` lub overflow przez północ
> 6. **Hot-reload tak/nie** — i co się dzieje przy zmianie
> 7. **Przykład minimalny** + **przykład pełny**
> 8. **Migracja wersji** — jak zachować się przy starszej wersji configu (pole `config_version`)
>
> Pliki do udokumentowania:
> - `config/config.yaml` (główny, ~30 kluczy z PRD_04)
> - `config/commands.yaml` (custom komendy)
> - `config/game_profiles/*.yaml` (per-game, full schema)
> - `personas/*.md` (frontmatter YAML + body Markdown — strukturyzowany)
> - `data/player_profile.yaml` (wieloznakowy profil)
>
> Sekcje dodatkowe:
> - **Loader behavior** — kolejność: env vars → user config → defaults → walidacja → save normalized version
> - **Error handling** — co robić gdy `config.yaml` nieparsowalny (load defaults + log + ostrzeżenie głosem)
> - **Migracje** — gdy schema się zmienia między wersjami: skrypt `migrate_config.py`
> - **Tabela mapowania**: klucz config → który komponent z niego korzysta (np. `audio.stt_confidence_threshold` → `STTEngine`, `Orchestrator`)
>
> Użyj **Pydantic V2** dla schemy Python (z `Field(..., ge=, le=)`).

**Akceptacja:** Każdy klucz z PRD_04 ma typ, default, walidację. Niejasności rozwiązane (np. `proactivity_level: passive | moderate | active` — co dokładnie różni je behawioralnie? — to powinno być w słowniku DOK-01).

**Pytania do użytkownika przed promptem:**

> ❓ **Dla użytkownika przed wygenerowaniem DOK-03:**
> 1. Co ma być źródłem prawdy gdy istnieje **i** zmienna środowiskowa **i** klucz w config.yaml? (env > config? config > env?)
> 2. Czy chcesz aby asystent powiedział głosowo o błędach w konfigu (degraded mode), czy tylko zalogował?
> 3. Czy `quiet_hours` ma być per-day-of-week, czy globalne (jak w PRD)?

---

## DOK-04: API_CONTRACT.md — Kontrakt REST + WebSocket

**Po co:** Frontend i backend są pisane w różnych językach (Python/JS). Kontrakt = single source of truth. PRD podaje 5 endpointów i 5 eventów — niewystarczające.

**Materiały źródłowe:**
- PRD_04_ARCHITECTURE.md (sekcja Komunikacja Frontend ↔ Backend)
- PRD_02_FUNCTIONAL.md (UI wymagania)
- PRD_05_UX_BEHAVIOR.md (audio duck, text overlay, statusy)

**Prompt:**

> Wygeneruj `API_CONTRACT.md` — kompletny kontrakt komunikacji między backendem (FastAPI) a frontendem (Electron) projektu Assystent.
>
> Dwie sekcje główne:
>
> **A) REST API**
> Dla każdego endpointu:
> - Method + Path (`GET /status`)
> - Path params, Query params, Request body (JSON Schema)
> - Response 200/4xx/5xx z przykładami JSON
> - Idempotencja, rate limit (jeśli dotyczy)
> - Autoryzacja (lokalnie: czy potrzebna? token w localhost?)
>
> Endpointy minimum (rozszerz jeśli widzisz potrzebę):
> - `GET /health` — liveness probe
> - `GET /status` — pełny stan (health, VRAM, wątki, observer, circuit breaker, current persona, active session)
> - `GET /config` / `PUT /config` — odczyt/edycja konfiguracji (z hot-reload trigger)
> - `POST /observer/start` / `POST /observer/stop`
> - `POST /persona/change` (body: `{"name": "komentator"}`)
> - `POST /tts/speak` (body: tekst — do testów manualnych)
> - `POST /command/execute` (alternatywa do mowy — UI button → komenda)
> - `GET /sessions` / `GET /sessions/{id}/transcript`
> - `GET /documents` (lista wygenerowanych)
> - `GET /debug/last_interaction`
>
> **B) WebSocket Protocol** (`ws://localhost:8000/ws`)
> - Connection lifecycle: handshake → state sync → heartbeat (5s ping/pong) → reconnect logic
> - Format wiadomości: `{type: string, payload: {...}, timestamp: int}`
> - Eventy **server → client**:
>   - `audio_stream` — chunki PCM (format: sample rate, channels, encoding base64?)
>   - `audio_stream_end` — koniec utterance
>   - `emotion` — `{emotion, intensity, duration_ms}`
>   - `system_state` — zmiana stanu (listening/thinking/speaking/error/degraded)
>   - `text_overlay` — tryb cichy
>   - `config_update` — po hot-reload
>   - `notification_sound` — przed komentarzem obserwatora
>   - `observer_started` / `observer_stopped`
>   - `transcription_partial` / `transcription_final` — debug overlay
> - Eventy **client → server**:
>   - `ptt_start` / `ptt_end`
>   - `audio_chunk` (mikrofon → backend dla STT)
>   - `avatar_position_update` (drag&drop)
>   - `frontend_ready` (po reconnect — request state sync)
>   - `viewer_focused` / `viewer_blurred`
>
> Wymagane sekcje:
> - **State Sync after reconnect** — algorytm krok po kroku
> - **Backpressure** — co jeśli frontend nie nadąża z audio stream
> - **Audio format** — dokładnie: 16kHz / 22.05kHz, mono, PCM s16le, chunk size, base64 czy binary frames
> - **Error frames** — `{type: "error", payload: {code, message, recoverable: bool}}`
> - **Wersjonowanie protokołu** — pole `protocol_version` w handshake
>
> Wygeneruj również **OpenAPI 3.0 YAML** dla REST endpointów (jako osobny plik `openapi.yaml` w treści).

**Akceptacja:** Frontend developer może zrobić mocka backendu na podstawie samego dokumentu. Wszystkie 5 evenów z PRD_04 są zdefiniowane i rozszerzone.

---

## DOK-05: PROMPT_SPEC.md — Specyfikacja Promptów i Function Calling

**Po co:** PRD definiuje strukturę "base + persona + game + observer + player" ale nie ma konkretnego tekstu base prompta, formatu function schemas dla 6 narzędzi, ani zasad łączenia.

**Materiały źródłowe:**
- PRD_02_FUNCTIONAL.md (sekcja AI/LLM, MCP Tools)
- PRD_05_UX_BEHAVIOR.md (Język i Komunikacja, Persona)
- PRD_01_VISION.md (zachowanie ogólne)

**Prompt:**

> Wygeneruj `PROMPT_SPEC.md` — kompletna specyfikacja systemu promptów i function calling dla projektu Assystent.
>
> **Sekcje:**
>
> 1. **Base System Prompt (PL)** — pełny, gotowy do użycia tekst (~300-500 słów):
>    - Tożsamość: jesteś asystentem AI lokalnym, masz awatar
>    - Język: PL domyślny, EN na żądanie, oryginalne tytuły
>    - Format odpowiedzi: krótkie zdania (czytane głosem), bez markdown w głosie, max ~80 słów per odpowiedź jeśli rozmowa
>    - Tag emocji: `[EMO:nazwa]` na początku każdej odpowiedzi (lista 16 dozwolonych)
>    - Function calling: kiedy używać (web_search dla świeżych info, calculator dla obliczeń itd.)
>    - Co robić przy niepewności: szukać, nie zmyślać
>    - Brak halucynacji o czasie: zawsze `get_current_time` jeśli pytanie o "dziś", "teraz"
>    - Sandbox: nie obiecywać akcji których nie możesz wykonać (otworzyć aplikację, zmienić ustawienia OS)
>
> 2. **Persona Prompt Format** — schemat pliku `.md` z frontmatter:
>    ```yaml
>    ---
>    name: default
>    display_name: "Sarkastyczny Kompan"
>    proactivity: moderate
>    tts_emotion_bias: amused  # bazowa emocja gdy brak [EMO:]
>    ---
>    
>    ## Osobowość
>    ...
>    ```
>    + reguły mergowania z base promptem (persona NIE nadpisuje sandbox/language rules — tylko ton)
>
> 3. **Dynamic Prompt Builder** — algorytm w pseudokodzie i Python:
>    - Kolejność sekcji
>    - Przycinanie do `max_context_tokens` (priorytety: base > persona > history > observer > player)
>    - Format każdej sekcji (nagłówek, zawartość)
>    - Decyzja: kiedy włączyć `[GAME_PROFILE]` (gra wykryta + obserwator aktywny)
>    - Decyzja: ile ostatnich wiadomości w historii (z DB_SCHEMA: 20 non-observer + 5 semantic + 1-2 observer)
>
> 4. **Function Calling Schemas** — pełny JSON Schema dla każdego z 6 narzędzi (OpenAI tool format):
>    - `web_search(query: str, max_results: int = 5)` → returns `[{title, url, snippet}]`
>    - `web_scraper(url: str)` → returns `{title, content_markdown, fetched_at}`
>    - `get_current_time(timezone: str = "Europe/Warsaw")` → returns `{iso, weekday, hour}`
>    - `calculator(expression: str)` → returns `{result, error}`
>    - `generate_document(topic: str, format: "md"|"html", content: str, filename_hint: str)` → returns `{file_path, file_size}`
>    - `screen_capture(focus_cursor: bool = false, prompt: str)` → returns `{description, ocr_text}`
>    + dla każdego: kiedy LLM **powinien** wywołać, kiedy **nie powinien** (np. nie szukać czasu w internecie — użyć tool), edge cases
>
> 5. **Observer Comment Prompt** — osobny prompt do generowania komentarzy w pętli obserwatora (krótszy, bardziej imperatywny: "Skomentuj scenę jednym zdaniem jeśli wydarzyło się coś istotnego, w przeciwnym razie zwróć `[SKIP]`")
>
> 6. **Game-specific addendum** — jak z `game_profiles/poe2.yaml.context_prompt` budować dodatek do system prompta
>
> 7. **Examples** — 5 par (input → expected LLM output) pokazujące:
>    - Pytanie ogólne (no tool)
>    - Pytanie wymagające web_search
>    - Komentarz observera (skip case)
>    - Komentarz observera (alert case)
>    - Generowanie dokumentu (multi-tool sequence)
>
> 8. **Anty-patterny** — czego LLM ma NIE robić: nie używać markdown formattingu w głosie, nie pisać "jako AI nie mogę…", nie powtarzać taga `[EMO:]` w środku zdania, nie wywoływać tych samych narzędzi w pętli.
>
> Każdy prompt: gotowy do skopiowania, bez placeholderów typu `[FILL_THIS]`.

**Akceptacja:** Można skopiować base prompt do LM Studio i zacząć rozmawiać. Function schemas waliduje się z OpenAI Python SDK.

**Pytania do użytkownika przed promptem:**

> ❓ **Dla użytkownika przed wygenerowaniem DOK-05:**
> 1. Czy długość odpowiedzi w trybie głosowym ma być twardo limitowana (np. max 80 słów) czy soft hint?
> 2. Czy chcesz aby LLM mógł odpowiedzieć "nie wiem i nie znalazłem" zamiast halucynować, gdy MCP nie pomógł? (W jakim tonie — przeprosić, zażartować?)
> 3. Czy persony mogą wpływać na decyzje o tool use (np. persona "minimalistyczna" → mniej tool calls)?

---

## DOK-06: EMOTION_SPEC.md — Specyfikacja Emocji i Animacji

**Po co:** PRD wymienia 16 emocji, mapowanie na blendshapes, aurę i body, oraz modulację TTS — ale to high-level. Brakuje: dokładnej listy blendshapes per emocja, krzywych animacji, intensywności, transition timing.

**Materiały źródłowe:**
- PRD_02_FUNCTIONAL.md (sekcja Awatar 3D)
- PRD_05_UX_BEHAVIOR.md (TTS Emotion Modulation)

**Prompt:**

> Wygeneruj `EMOTION_SPEC.md` — kompletna specyfikacja systemu emocji projektu Assystent. To dokument referencyjny dla developera frontend (Three.js) i backend (TTS modulation).
>
> Dla **każdej z 16 emocji** (happy, amused, proud, sympathetic, sad, disappointed, angry, disgusted, excited, scared, surprised, nervous, thinking, confused, nostalgic, sarcastic):
>
> ```
> ## happy
> - **Triggers (przykłady kontekstów)**: gracz osiągnął sukces, daily check pozytywny, powitanie
> - **VRM Blendshapes**:
>   - Primary: Happy (1.0)
>   - Secondary: Joy (0.6), Eye_Smile (0.8)
>   - Conflict: nie używać razem z Sad/Angry
> - **Aura**:
>   - Color: #FFD700 (złoty)
>   - Intensity: 0.7
>   - Pulse: tak, 1.5Hz
> - **Body Animation (procedural)**:
>   - Head tilt: 5° prawo, oscylacja ±2°
>   - Body sway: ±3° na osi Z, 2Hz
>   - Hands: lekko uniesione (jeśli model ma full body)
>   - Single shot: lekkie podskoczenie translateY +0.05 z spring-back
> - **TTS modulation**: speed 1.1x, pitch +5%
> - **Duration**: min 2s, max 8s, fade-out 500ms
> - **Transition from**: dowolnej (smooth 300ms blend)
> - **Transition to**: dowolnej (300ms)
> ```
>
> Sekcje dodatkowe:
>
> 1. **Emotion Lifecycle** — diagram stanów: incoming → blending → holding → fading → idle
> 2. **Conflict Resolution** — co gdy nadejdzie nowa emocja w trakcie poprzedniej (override / queue / blend)
> 3. **Fallback Layers** — algorytm:
>    - Layer 1: blendshapes (jeśli model je wspiera)
>    - Layer 2: aura/shader (zawsze dostępne)
>    - Layer 3: body (jeśli VRMHumanoid pełny)
>    - Detection: skan modelu przy ładowaniu → JSON `model_capabilities.json`
> 4. **System Visual States** — 6 stanów (idle, listening, thinking, speaking, error, degraded) — każdy z konkretną wizualizacją (kolor aury, animacja). Te są **niezależne** od emocji LLM (mogą się kumulować: thinking + sad).
> 5. **Lip-sync** — algorytm: amplituda audio (RMS w okienku 50ms) → blendshape Mouth_A + drobne wariacje I/O/U na podstawie formantów (lub prościej: sama amplituda mapowana na 0-1 dla `Vrm.Expressions.aa`). Sample rate, latency target <100ms.
> 6. **Emotion Tag Parser** — regex i logika usuwania `[EMO:nazwa]` z tekstu przed TTS, walidacja nazwy emocji, fallback do `neutral` przy nieznanej.
> 7. **Default Emotion** — gdy LLM nie zwróci taga: użyj `persona.tts_emotion_bias` lub `neutral`.
> 8. **Tabela TTS** — speed/pitch z PRD_05 + dodaj `formant_shift` jeśli Piper/XTTSv2 wspiera.
> 9. **Test fixtures** — lista plików `.vrm` testowych (capabilities matrix: ile blendshapes każdy ma) + jakie zachowanie oczekiwane.
>
> Format wyjściowy: Markdown + osobny `emotions.json` (machine-readable, używany w runtime przez frontend).

**Akceptacja:** Frontend developer dostaje `emotions.json` i implementuje bez dodatkowych pytań. Każda emocja ma 4 warstwy w pełni opisane.

---

## DOK-07: COMMANDS_SPEC.md — Specyfikacja Komend Systemowych

**Po co:** PRD podaje listę komend i przykład YAML, ale brakuje formalnej gramatyki, obsługi konfliktów, lokalizacji (PL/EN), priorytetów, i zachowania przy częściowym dopasowaniu.

**Materiały źródłowe:**
- PRD_02_FUNCTIONAL.md (sekcja Komendy Systemowe)
- PRD_05_UX_BEHAVIOR.md (komendy w User Stories)

**Prompt:**

> Wygeneruj `COMMANDS_SPEC.md` — pełna specyfikacja systemu komend systemowych w projekcie Assystent.
>
> Sekcje:
>
> 1. **Wbudowane komendy** — tabela ze wszystkimi 13 komendami z PRD_02 + dodatki:
>    | ID | Nazwa | Triggery PL | Triggery EN | Parametry | Akcja (handler) | Confirmation |
>    
>    Dla każdej komendy: 3-5 wariantów triggerów (np. "idź spać" / "śpij" / "wyłącz się" / "dobranoc"), confirmation policy (auto / verbal / none).
>
> 2. **Format `commands.yaml`** — pełna schema z walidacją:
>    ```yaml
>    version: 1
>    commands:
>      - id: change_persona
>        triggers:
>          - pattern: "zmień personę na {name}"
>            language: pl
>          - pattern: "bądź {name}"
>            language: pl
>          - pattern: "switch to {name} persona"
>            language: en
>        params:
>          name:
>            type: string
>            choices: ${personas_available}  # dynamiczne
>        action: change_persona
>        priority: 50
>        confirmation: none
>        cooldown_seconds: 0
>    ```
>
> 3. **Parser i Pipeline** — diagram:
>    ```
>    transcription → normalize (lowercase, no diacritics)
>                  → match against built-in commands (priority order)
>                  → match against custom commands.yaml
>                  → confidence ≥ threshold → execute
>                  → else → forward to LLM
>    ```
>
> 4. **Algorytm matchingu** — regex + named groups + fuzzy matching (np. Levenshtein distance ≤ 2 dla tolerancji STT errors). Konfigurowalny: `command_match_fuzzy: bool`.
>
> 5. **Lista handlerów** — interfejs Python:
>    ```python
>    class CommandHandler(Protocol):
>        async def execute(self, params: dict, context: Context) -> CommandResult: ...
>    ```
>    + implementacja każdej komendy (1-2 zdania what + dependencies)
>
> 6. **Priorytetyzacja** — gdy 2 komendy pasują (np. "obserwuj" matches "zacznij obserwować"): wyższy `priority` wins, przy równym — pierwsza w pliku.
>
> 7. **Lokalizacja** — która komenda działa w PL/EN/both.
>
> 8. **Confirmation patterns** — np. komenda "Zrób backup" wymaga "Tak, zrób backup" w follow-up (1 turn timeout).
>
> 9. **Cooldowns i rate limits** — np. "Zrób backup" max 1x na 5 minut.
>
> 10. **Edge cases**:
>     - Komenda w środku dłuższej wypowiedzi: "tak, dobra, idź spać teraz proszę" — czy wykrywać?
>     - Negacja: "nie idź spać"
>     - Kontekst: po pytaniu "Mam zrobić backup?" odpowiedź "tak" → execute
>     - Multi-command w jednym utterance: "zacznij obserwować i zmień personę na komentator"
>
> 11. **Custom Commands DSL** — przykłady 3-5 custom komend z różnymi typami parametrów (number, string, choice, optional).
>
> 12. **Rejestracja handlera** — gdzie w kodzie i jak dodać nowy handler dla custom komendy.
>
> 13. **Testy** — lista przypadków testowych (input → expected match), w tym false positives.

**Akceptacja:** Wszystkie 13 komend z PRD są opisane z 3+ triggerami w PL. Schema YAML walidacyjna. Edge case "tak, dobra, idź spać teraz" rozstrzygnięty.

**Pytania do użytkownika przed promptem:**

> ❓ **Dla użytkownika przed wygenerowaniem DOK-07:**
> 1. Czy chcesz aby fuzzy matching był domyślnie włączony (większa tolerancja STT) czy wyłączony (większa precyzja)?
> 2. Komenda "Zrób backup" — wymaga potwierdzenia czy nie? (PRD mówi raczej nie, ale to destrukcyjne-ish)
> 3. Czy custom komendy mogą wywoływać MCP tools (np. user definiuje "sprawdź pogodę" → web_search)?

---

## DOK-08: ALGORITHMS_SPEC.md — Specyfikacja Algorytmów Krytycznych

**Po co:** PRD opisuje GPU Scheduler, Circuit Breaker, Session Watchdog, Rate Limiter, Cache hasłami. Implementacja wymaga dokładnych algorytmów z edge cases.

**Materiały źródłowe:**
- PRD_03_NONFUNCTIONAL.md (GPU Scheduler, priorytety, baseline)
- PRD_01_VISION.md (Circuit Breaker, SessionWatchdog)
- PRD_02_FUNCTIONAL.md (Cache MCP, Rate Limiter)
- DB_SCHEMA.md (mcp_cache, system_state)

**Prompt:**

> Wygeneruj `ALGORITHMS_SPEC.md` — pełna specyfikacja algorytmów krytycznych projektu Assystent. Każdy algorytm: cel, pseudokod, implementacja Python, testy, edge cases.
>
> Algorytmy do udokumentowania:
>
> 1. **GPU Scheduler** (mutex z priorytetami)
>    - Struktura: `asyncio.PriorityQueue` lub własna `PriorityLock`
>    - 4 priorytety (1=najwyższy STT, 2=LLM, 3=TTS, 4=VLM)
>    - Preemption: czy wyższy priorytet przerywa niższy? (NIE — czeka na zakończenie)
>    - Starvation prevention: priority aging (po 30s w kolejce → bump up)
>    - Timeout per task (60s default)
>    - Metryki: avg wait time, queue depth
>
> 2. **Circuit Breaker** (LM Studio + MCP web_search)
>    - States: CLOSED, OPEN, HALF_OPEN
>    - Triggery: 3 consecutive failures → OPEN
>    - Recovery: 30s → HALF_OPEN → 1 probe → success → CLOSED
>    - Persistence: stan w `system_state` table (przeżywa restart? — TAK z TTL)
>    - Per-endpoint czy global? — per-endpoint
>    - Failure classification: timeout vs 5xx vs network — wszystkie liczą się
>
> 3. **Session Watchdog** (hibernation recovery)
>    - Pętla async co 5s: `now - last_tick > 30s` → hibernation detected
>    - Recovery sequence:
>      1. Mark current session `health_state = 'resumed_after_hibernate'`
>      2. Reconnect WebSocket (frontend)
>      3. Ping LM Studio (retry 5x co 5s)
>      4. Reinit mikrofonu (PyAudio device probing)
>      5. Emit emotion `confused` → `happy` z TTS "O, wróciłeś!"
>    - Crash detection: na startup query `WHERE ended_at IS NULL` → mark crashed
>
> 4. **Rate Limiter** (web_search 10 req/min)
>    - Token bucket algorithm
>    - Persistent counter w `system_state` (key: `web_search_tokens`, refill schedule)
>    - Behavior on exhaustion: reject + emit emotion `disappointed`
>    - Burst handling
>
> 5. **MCP Cache** (SHA256 key, TTL)
>    - Key generation: `SHA256(tool_name + canonical_json(params))` — algorytm kanonikalizacji JSON (sorted keys, no whitespace)
>    - TTL per tool (86400 / 604800 / 0)
>    - Hit count tracking
>    - Cleanup strategy: lazy (przy `get`) + scheduled (startup)
>    - Bypass: parametr `force_refresh: bool` lub komenda "Odśwież informacje"
>    - Cache stampede prevention: lock per cache_key
>
> 6. **Observer Loop**
>    - Pętla async co `observer_interval_seconds`
>    - Skip warunki: PTT aktywny, tryb sleep, brak gry, scene_hash identyczny ostatnim 3 (deduplikacja statycznych scen)
>    - Backpressure: jeśli VLM nie nadąża → skip cycle (nie kolejkuj)
>    - Cancel: na komendę "Przestań obserwować" lub PTT (wstrzymanie)
>
> 7. **Scene Change Detection** (opcjonalne F-OB-07)
>    - Algorytm: dHash perceptual hash, threshold Hamming distance > 8
>    - Fallback: zawsze analizuj jeśli `scene_change_detection: false` w configu
>
> 8. **Audio Duck**
>    - Trigger: `ptt_start` event
>    - Action: TTS volume → 0 w 200ms (linear ramp via WebSocket lub bezpośrednio w audio sink)
>    - Restore: po `ptt_end` lub anulowanej interakcji
>
> 9. **Streaming Response Pipeline**
>    - LLM stream tokens → buffer → split na zdania (regex `[.!?]\s+`) → kolejkuj per-zdanie do TTS → TTS generuje → audio queue → WebSocket
>    - First sentence latency target <1.5s
>
> 10. **ChromaDB Rotation FIFO**
>     - Z DB_SCHEMA: limit 10k, batch 100, atomic delete (chroma + null reference w SQLite)
>     - Trigger: gdy `count() ≥ limit`
>     - Co rotuje: include_in_semantic_memory=1 AND archived=0
>
> 11. **Daily Meta Check**
>     - Trigger przy starcie: jeśli `last_meta_check < now - 24h`
>     - Background thread (nie blokuje startupu)
>     - Sequence: enumerate active games z player_profile → web_search per game → ingest do knowledge_base → record w daily_checks
>     - Notification: po starcie sesji, gdy obserwator NIE aktywny (nie spamuj w trakcie gry)
>
> 12. **Auto-Archive Logs**
>     - Cron-like: codziennie o godzinie z quiet_hours
>     - Find logs > 30 dni → kompresja → przeniesienie do `logs/archive/`
>     - Verify integrity przed delete oryginału
>
> Dla każdego algorytmu sekcja **Test Cases**: 3-5 scenariuszy z input/expected output (jednostkowo testowalne).

**Akceptacja:** Dla każdego algorytmu: sekwencja diagram (jeśli złożony), kod Python (testowalny), edge cases. Implementator może pisać kod bez improwizacji.

---

## DOK-09: OBSERVER_SPEC.md — Specyfikacja Trybu Obserwatora

**Po co:** Obserwator to najbardziej złożony moduł (3 typy, kaskadowa detekcja gier, dual VLM+OCR pipeline). PRD opisuje to wysokopoziomowo.

**Materiały źródłowe:**
- PRD_02_FUNCTIONAL.md (sekcja Tryb Obserwatora)
- DB_SCHEMA.md (game_detections, player_context_snapshots)
- DOK-05 (PROMPT_SPEC) i DOK-08 (ALGORITHMS) jako źródło spójności

**Prompt:**

> Wygeneruj `OBSERVER_SPEC.md` — pełna specyfikacja modułu obserwatora projektu Assystent.
>
> Sekcje:
>
> 1. **Trzy typy obserwatora** — szczegółowy opis każdego (Game Observer, On-demand Query, Ambient Observer): trigger, lifecycle, schemat capture+analysis, output, side effects.
>
> 2. **Game Detection — kaskadowy algorytm**:
>    - Krok 1: `psutil.process_iter()` skanowane co 5s, match przeciw `game_profiles/*.process_names`
>    - Krok 2: Jeśli brak match a obserwator aktywny → screenshot + VLM prompt "Czy to gra? Jaka?" → match po nazwie
>    - Krok 3: Manual override przez komendę "Gram teraz w X"
>    - Persistence: `game_detections` table — record start/end gry
>    - Disambiguation: kilka procesów pasuje (np. uruchomione 2 gry) → pierwszy wykryty + log warning
>
> 3. **Game Profiles — schema YAML**:
>    - Wszystkie pola z PRD_02 example (poe2.yaml)
>    - + brakujące: `mcp_sources`, `screen_regions`, `vlm_prompt_template`, `comment_styles` (lista wzorców komentarzy do losowania), `silence_after_comment_seconds`
>    - 2 przykłady: poe2.yaml (action), stellaris.yaml (strategic)
>
> 4. **Capture Pipeline**:
>    - DXcam config (region, target FPS dla obserwatora — np. 1 FPS aby nie marnować zasobów)
>    - Screen regions: jak wyciąć (procentowo z `screen_regions` w profilu)
>    - Multi-monitor: który ekran (`config.observer.monitor_index` lub aktywne okno gry przez `pygetwindow`)
>    - Frame storage: in-memory only, bez zapisu (chyba że `debug.save_screenshots`)
>
> 5. **VLM Pipeline**:
>    - Prompt do VLM (Moondream2): generic "Opisz scenę z gry [game_name]. Skup się na: [focus_areas]"
>    - Output parsing: free text, max 200 słów
>    - Detekcja "scena z tooltip/UI/item" → trigger OCR pipeline
>    - Detekcja statycznej sceny (dHash): skip
>    - Per-game prompt customization z `vlm_prompt_template`
>
> 6. **OCR Pipeline (dual)**:
>    - Trigger: VLM zwrócił sygnał "tooltip detected" lub regex zgodny z item descriptor
>    - Crop strategy: bounding box detection (heurystyka koloru/ramki) lub fixed regions per profile
>    - EasyOCR config: język ['en'] + opcjonalnie ['pl'], GPU
>    - Post-processing: filtrowanie noise (krótkie tokeny, znaki specjalne)
>
> 7. **Comment Generation**:
>    - Prompt do LLM: VLM_output + OCR_output + game_profile.context + active_character/build z player_profile
>    - LLM zwraca komentarz lub `[SKIP]` (jeśli scena nieistotna)
>    - Limit: 1 komentarz na N sekund (`silence_after_comment_seconds` per profile, default 30)
>    - Diversity: nie powtarzać tego samego komentarza dwa razy z rzędu (cosine similarity >0.85 ostatnich 3 → skip)
>
> 8. **On-demand Screen Query**:
>    - Trigger: STT match na "co widzisz", "co tu jest", "wytłumacz mi tę stronę" (regex w COMMANDS_SPEC + LLM intent classification fallback)
>    - Capture: full screen + crop 600x400 wokół `pyautogui.position()`
>    - VLM prompt: "Kursor na (x,y). Skup się na elemencie pod kursorem. Opisz dla osoby pytającej."
>    - Brak zapisu w observer table — to jest interaction
>
> 9. **Pause/Resume**:
>    - PTT aktywny → pauza pętli
>    - `Conversation Lock` state → pauza
>    - Po zakończeniu interakcji + 2s grace period → resume
>
> 10. **Lifecycle Events** (DB writes):
>     - Start: `game_detections.started_at`
>     - Każdy komentarz: `messages` row z `source='observer'` i `scene_hash`
>     - Snapshot kontekstu: `player_context_snapshots` przy zmianie gry/postaci
>     - Stop: `game_detections.ended_at`
>
> 11. **Error Handling**:
>     - DXcam fail (np. fullscreen exclusive) → fallback do `mss` library + log warning
>     - VLM timeout (>10s) → skip cycle, emit `nervous` emotion przy 3 z rzędu
>     - OCR fail → kontynuuj tylko z VLM output
>     - Game crash detected (proces zniknął) → "Game over!" emotion `surprised`, stop observer
>
> 12. **Performance**:
>     - Target: <5% FPS impact (z PRD)
>     - Mierniki: capture latency, VLM latency, full cycle time
>     - Tuning knobs: interval, scene change detection, OCR enable/disable per profile

**Akceptacja:** Każdy z 3 typów obserwatora ma flow chart. Game profile YAML waliduje się ze spec. Pipeline VLM+OCR jest deterministyczny.

**Pytania do użytkownika przed promptem:**

> ❓ **Dla użytkownika przed wygenerowaniem DOK-09:**
> 1. Czy mając Stellaris i PoE2 jako primary games — masz dostęp do screenshotów obu, czy mam zaproponować generic prompt VLM?
> 2. Czy minimalnie używamy `pygetwindow` do detekcji aktywnego monitora gry, czy zawsze konfiguracja statyczna `config.observer.monitor_index`?
> 3. OCR — chcesz aby był włączony domyślnie tylko dla `observer_type: action` (PoE2), czy zawsze?

---

## DOK-10: MCP_TOOLS_SPEC.md — Specyfikacja MCP Tools

**Po co:** PRD definiuje 6 narzędzi z TTL i rate limitami. Brakuje: dokładnej sygnatury każdego, error handling, sandbox enforcement, testów.

**Materiały źródłowe:**
- PRD_02_FUNCTIONAL.md (sekcja MCP Tools)
- PRD_03_NONFUNCTIONAL.md (sandbox)
- DOK-05 (PROMPT_SPEC) — function schemas
- DB_SCHEMA.md (mcp_cache, tool_calls)

**Prompt:**

> Wygeneruj `MCP_TOOLS_SPEC.md` — pełna specyfikacja 6 narzędzi MCP w projekcie Assystent.
>
> Dla **każdego narzędzia** sekcja:
>
> ```
> ## Tool: web_search
> 
> ### Sygnatura
> ```python
> async def web_search(
>     query: str,
>     max_results: int = 5,
>     site: str | None = None,
>     freshness_days: int | None = None,
> ) -> WebSearchResult: ...
> ```
> 
> ### Schema OpenAI tool
> { ... pełny JSON schema ... }
> 
> ### Implementacja
> - Backend: DuckDuckGo via `duckduckgo-search` library / SearXNG self-hosted (configurable)
> - Brak klucza API
> - Cache: TTL 24h dla "game meta" queries (heurystyka: keywords "build", "meta", "patch"), 1h dla reszty
> 
> ### Sandbox
> - DOZWOLONE domeny: wszystkie (web search z natury)
> - ZAKAZANE: nie wywołuj jeśli `online_mode = false`
> 
> ### Rate Limit
> - 10 req/min (token bucket)
> - On exceed: raise `RateLimitedError`, emit emotion `disappointed`
> 
> ### Error Handling
> - Network error → retry 2x z exponential backoff (1s, 3s) → fail z message
> - DDG blocked / captcha → fallback do SearXNG jeśli skonfigurowany
> 
> ### Output Format
> ```json
> [{"title": "...", "url": "...", "snippet": "...", "published_at": "ISO8601 | null"}]
> ```
> 
> ### Cache Key
> SHA256("web_search" + canonical_json({query, max_results, site, freshness_days}))
> 
> ### Tool Call Logging
> Wszystkie wywołania → `tool_calls` table z `turn_sequence`, `success`, `duration_ms`
> 
> ### Test Cases
> 1. Happy path: query "PoE2 best build" → 5 results
> 2. Rate limit hit: 11 calls / 1min → 11. = RateLimitedError
> 3. Cache hit: identyczny query w <24h → DB read, brak network
> 4. Network down: ConnectionError → user-friendly message
> ```
>
> **Pełnij dla wszystkich 6:**
> 1. `web_search` (DuckDuckGo)
> 2. `web_scraper` (httpx + readability/trafilatura, fallback Selenium dla SPA?)
> 3. `get_current_time` (`datetime.now(timezone)`)
> 4. `calculator` (`asteval`, sandbox bezpieczny)
> 5. `generate_document` (Markdown + opcjonalnie HTML z template)
> 6. `screen_capture` (DXcam + VLM pipeline z DOK-09)
>
> Dodatkowe sekcje:
>
> A. **Sandbox enforcement layer** — wspólny code dla wszystkich tools, walidator ścieżek (whitelist `c:\ai\asystent\**`), rejector niedozwolonych operacji
>
> B. **Tool registry** — gdzie deklarujemy wszystkie tools, jak LLM dostaje listę (per turn refresh? cache?)
>
> C. **Tool call lifecycle** — DB flow:
>    1. LLM zwraca `tool_calls` w response
>    2. Orkiestrator: dla każdego tool → INSERT row do `tool_calls` (turn_sequence)
>    3. Execute tool → UPDATE row z output_json, success, duration_ms
>    4. Append tool result do conversation → re-query LLM
>    5. Limit: max 5 tool calls per turn (z PRD)
>
> D. **Generate Document — special case** — nie liczy się do limitu 5, output to filename (nie content w response)
>
> E. **Online mode detection** — detekcja internetu (ping 1.1.1.1 co 30s w background) → flag w `system_state`. Tools z grupy "online" (web_search, web_scraper) zwracają `OfflineModeError` i emit emotion `disappointed`.
>
> F. **HTML Generator detail** — jak działa template, dark/light theme switch, Mermaid offline fallback (gdy brak CDN), CSS embedding (single-file output)

**Akceptacja:** Każde narzędzie ma sygnaturę, schema, error cases. Online mode degraduje gracefully. Sandbox aktywny zawsze.

**Pytania do użytkownika przed promptem:**

> ❓ **Dla użytkownika przed wygenerowaniem DOK-10:**
> 1. `web_scraper` — czy chcesz fallback Selenium/Playwright dla stron SPA (np. maxroll.gg), czy wystarczy "tekst statyczny + jeśli nie da się — pyt user konwersacyjnie"? (Selenium = +500MB zależności)
> 2. `web_search` — preferujesz DuckDuckGo lokalnie (zero setup) czy zachęcam do self-hosted SearXNG (lepsza prywatność, więcej setupu)?
> 3. Czy `generate_document` może nadpisywać istniejący plik o tej samej nazwie, czy zawsze unikalny suffix?

---

## DOK-11: MEMORY_SPEC.md — Specyfikacja Pamięci i Persystencji

**Po co:** DB_SCHEMA jest świetny, ale to "co". Brakuje "jak": kiedy zapisujemy, kiedy odzyskujemy, jak budujemy semantic recall, kiedy archive itd.

**Materiały źródłowe:**
- DB_SCHEMA.md (cały)
- PRD_02_FUNCTIONAL.md (sekcja Pamięć i Persystencja)
- PRD_06 (auto-archive)

**Prompt:**

> Wygeneruj `MEMORY_SPEC.md` — pełna specyfikacja warstwy pamięci projektu Assystent. Załączam DB_SCHEMA jako bazę.
>
> Sekcje:
>
> 1. **Repository Pattern — Interfejsy**
>    - `MessageRepository`, `SessionRepository`, `ToolCallRepository`, `DocumentRepository`, `MCPCacheRepository`, `PlayerSnapshotRepository`, `DailyCheckRepository`, `GameDetectionRepository`, `HealthEventRepository`, `SystemStateRepository`
>    - Każdy: 5-8 metod (CRUD + specific queries)
>    - Bazowy `BaseRepository` z connection management
>
> 2. **Storage Backend Abstraction**
>    - `StorageBackend` ABC — implementacje: `SQLiteBackend`, future `PostgresBackend`, `GcpFirestoreBackend`
>    - Migration path: jak swap (config + restart, zero data loss)
>
> 3. **Message Save Pipeline**
>    - User message → INSERT do messages → INSERT embedding do ChromaDB (jeśli `include_in_semantic_memory`) → UPDATE chroma_embedding_id w SQLite
>    - Decision matrix: kiedy `include_in_semantic_memory = TRUE`:
>      - source='user' → ZAWSZE
>      - source='assistant' AND length > 100 chars → TRUE
>      - source='observer' → ZAWSZE FALSE (zalewałby pamięć)
>      - source='system' → ZAWSZE FALSE
>      (konfigurowalny w przyszłości)
>
> 4. **Semantic Recall Algorithm**
>    - Input: query (np. "co mówiłem o tym buildzie?"), opcjonalnie: game filter, k_conv, k_know
>    - Step 1: query ChromaDB.conversations (k=3 default) — filtered by `source IN ('user','assistant')`
>    - Step 2: query ChromaDB.knowledge_base (k=2 default) — filtered by game jeśli aktywna
>    - Step 3: deduplikacja (cosine sim >0.95 → keep one)
>    - Step 4: format dla prompta:
>      ```
>      [Wcześniejsze wspomnienia]
>      - 3 dni temu: "..."
>      - tydzień temu: "..."
>      [Wiedza o grze (PoE2)]
>      - "..."
>      ```
>    - Triggers: każda interakcja z LLM (chyba że `disable_semantic_recall: true`)
>
> 5. **Knowledge Base Ingestion**
>    - Folder watcher na `c:\ai\asystent\knowledge\**\*.md`
>    - Change detection: `mtime` w `metadata.file_updated_at`
>    - Chunking: split markdown po sekcjach (`#`, `##`), max 500 tokens, overlap 50 tokens (heurystyka)
>    - Re-ingestion: usuń stare chunki dla `source_file` → INSERT nowe
>    - Daily check artifacts → ingestion automatyczny po web_search → write `knowledge/{game}/daily_{date}.md`
>
> 6. **ChromaDB Rotation FIFO** (rozszerzenie z DB_SCHEMA)
>    - Trigger frequency: po każdym INSERT (sprawdź count) lub batch co N (cheaper)
>    - Atomicity: chroma.delete → SQLite.update — jeśli drugi fail, retry 3x; jeśli nadal fail → log + alert (rare)
>    - Metryki: rotation count, last rotation timestamp
>
> 7. **Player Profile Management**
>    - YAML jako source of truth (jak w DB_SCHEMA decyzja #3)
>    - SQLite snapshoty: dla promptu (szybki read), nie do pisania
>    - Update flow:
>      - User: "Gram teraz TankMasterem" → komenda `change_active_character` → `PlayerProfileRepository.set_active(game, char)` → UPDATE YAML → INSERT snapshot
>    - Multi-character: pełna struktura z PRD_02 example
>    - Build import: parsing maxroll/PoE Ninja URL → fields → user confirms → save
>
> 8. **Snapshot Triggers** (z DB_SCHEMA decyzja #7)
>    - `session_start` — at session creation
>    - `character_change` — after `change_active_character`
>    - `game_detected` — after `GameDetector` confirmed
>    - Każdy trigger jest oddzielnym INSERT, nie UPSERT — to historia
>
> 9. **Auto-Archive Strategy**
>    - Per session: gdy `session.created_at < now - 90 days` → mark `messages.archived=TRUE` (nie usuwa, oznacza)
>    - Logs: pliki `.md` > 30 dni → kompresja `.7z` z `py7zr` → przeniesienie do `logs/archive/` → delete oryginału (po sukcesie kompresji)
>    - Verification: rozpakuj losowy archiwum 1x w miesiącu (sanity)
>
> 10. **Backup/Restore**
>     - Komenda "Zrób backup" → `zipfile.ZipFile` → cały `c:\ai\asystent\` → `backups/assystent_backup_{ISO}.zip`
>     - Exclusions: `data/memory/*.bin` (ChromaDB index — może być rebuilt z conversations)
>     - Restore: instrukcja manualna w README (rozpakuj → restart)
>     - Konfigurowalny path docelowy
>
> 11. **Season Reset Detection**
>     - MCP web_search wykrywa keywords "new league", "season reset" w wynikach + porównanie z `player_profile.games.{game}.league`
>     - Asystent **pyta** głosowo: "Wygląda na nowy sezon. Reset profilu?"
>     - Confirm → `PlayerProfileRepository.archive_season(game, current_league_name)` → INSERT do `player_profile_archives` + reset characters list w YAML
>
> 12. **Schema Migrations**
>     - Pliki `001_initial.sql`, `002_*.sql` — numerowane
>     - Runner: `MigrationRunner.up()` — aplikuje brakujące, zapisuje w `schema_migrations`
>     - Brak `down` migrations w MVP (forward-only)
>
> 13. **Test Strategy**
>     - SQLite `:memory:` dla unit testów
>     - ChromaDB `EphemeralClient()` dla testów semantic recall
>     - Fixture: pre-loaded sessions z 100 messages, 20 z embeddingami → test recall accuracy
>
> 14. **Performance**
>     - Target: dowolne query < 50ms (przy <1M wiadomości)
>     - Indexy: każdy z DB_SCHEMA potwierdzony jako używany
>     - VACUUM strategy: weekend co tydzień (optional)

**Akceptacja:** Każdy repository ma interfejs, każdy use case (save, recall, archive) ma sequence diagram. Triggery snapshotów spójne z DB_SCHEMA.

---

## DOK-12: FRONTEND_SPEC.md — Specyfikacja Frontendu (Electron + React + Three.js)

**Po co:** Frontend to ~30% pracy z Fazy 3. PRD opisuje wymagania, ale brakuje: konkretnej struktury komponentów, lifecycle, jak ładować VRM, lip-sync algorithm.

**Materiały źródłowe:**
- PRD_02_FUNCTIONAL.md (sekcje Awatar, UI)
- PRD_05_UX_BEHAVIOR.md (Audio UX)
- PRD_04_ARCHITECTURE.md (Frontend stack)
- DOK-04 (API_CONTRACT)
- DOK-06 (EMOTION_SPEC)

**Prompt:**

> Wygeneruj `FRONTEND_SPEC.md` — pełna specyfikacja frontendu projektu Assystent.
>
> Sekcje:
>
> 1. **Architektura Electron**
>    - Process model: main + renderer (preload script)
>    - Window config: `frame: false, transparent: true, alwaysOnTop: true, resizable: true, webPreferences: { contextIsolation: true, nodeIntegration: false }`
>    - Multi-window: 1 window główne (awatar) + 1 modal config panel + system tray
>    - IPC: główne ↔ renderer dla globalnych hotkeys, system tray actions
>    - Click-through option: gdy `mouse_passthrough: true` → kliknięcia przez okno (do gry)
>
> 2. **System Tray**
>    - Ikona w `assets/tray-icon.png`
>    - Menu: Show/Hide, Restart Backend, Settings, Open Logs Folder, Quit
>    - State indicator (kolor ikony zmienia się: green/yellow/red wg health)
>
> 3. **Globalne Hotkeys**
>    - `Ctrl+Shift+A` — toggle visibility
>    - `Ctrl+Shift+S` — quick settings
>    - PTT key (configurable, default Caps Lock) — handled w backend (pynput), frontend tylko UI
>    - Konflikt: jeśli system zarejestrował już hotkey → emit `error` event z fallback
>
> 4. **Komponenty React** (struktura plików)
>    ```
>    src/
>    ├── App.jsx
>    ├── components/
>    │   ├── Avatar3D/
>    │   │   ├── Avatar3D.jsx          # główny renderer Three.js
>    │   │   ├── VRMLoader.js          # ładowanie + skan blendshapes
>    │   │   ├── EmotionController.js  # apply emotion z DOK-06
>    │   │   ├── LipSync.js            # algorithm
>    │   │   ├── IdleAnimations.js
>    │   │   └── AuraShader.js         # custom shader
>    │   ├── ConfigPanel/
>    │   │   ├── ConfigPanel.jsx
>    │   │   ├── AudioSettings.jsx
>    │   │   ├── AvatarSettings.jsx
>    │   │   ├── PersonaSelector.jsx
>    │   │   └── ObserverSettings.jsx
>    │   ├── StatusOverlay/
>    │   │   ├── StatusOverlay.jsx     # debug info, listening indicator
>    │   │   └── TextOverlay.jsx       # tryb cichy
>    │   └── SetupWizard/
>    │       └── SetupWizard.jsx       # first-run
>    ├── hooks/
>    │   ├── useWebSocket.js           # connection + reconnect z DOK-04
>    │   ├── useEmotion.js             # state + transitions
>    │   ├── useAudioPlayer.js         # audio queue + duck
>    │   └── useConfig.js              # GET/PUT config
>    ├── utils/
>    │   ├── api.js                    # REST client
>    │   ├── audio.js                  # PCM playback, ducking
>    │   └── constants.js
>    └── electron/
>        ├── main.js
>        ├── preload.js
>        └── tray.js
>    ```
>
> 5. **Avatar3D — szczegóły**
>    - Three.js setup: scene, camera (perspective, position dependent on window size), renderer (alpha: true, antialias)
>    - VRM loading: `@pixiv/three-vrm`, async load → callback z `model_capabilities` (lista blendshapes, bones)
>    - Render loop: `requestAnimationFrame`, target 60fps (jeśli okno widoczne, 30fps gdy minimized → power saving)
>    - Camera: head-and-shoulders default frame
>    - Lighting: 1x ambient + 1x directional + 1x rim light
>
> 6. **Lip-Sync Algorithm**
>    - Input: WebSocket audio chunk (PCM s16le 22050Hz mono)
>    - Compute RMS w okienku 50ms (Web Audio API: `AnalyserNode` + `getByteTimeDomainData`)
>    - Map RMS [0, 0.5] → blendshape `aa` [0, 1]
>    - Smoothing: lowpass filter (alpha=0.6) by uniknąć drgań
>    - Latency target: <100ms od audio do animacji
>    - Fallback gdy brak `aa` blendshape: open-mouth via VRMHumanoid jaw bone
>
> 7. **Emotion System Frontend** (z DOK-06)
>    - `useEmotion()` hook: subscribe do WebSocket `emotion` event
>    - Apply trzy warstwy: blendshapes → aura color/intensity → body procedural
>    - Transitions: 300ms blend między emocjami
>    - Z `emotions.json` ładowanym przy starcie
>
> 8. **Audio Player**
>    - Web Audio API: `AudioContext` + queue `AudioBufferSourceNode`
>    - PCM chunks z WebSocket → konwersja do AudioBuffer → enqueue
>    - Ducking: GainNode, smooth ramp 200ms
>    - Visualizer: feed do AnalyserNode (dla lip-sync + status indicator)
>
> 9. **WebSocket Client**
>    - Reconnect logic z DOK-04 (heartbeat, exponential backoff: 1s, 2s, 4s, 8s, max 30s)
>    - State sync after reconnect
>    - Buffer wiadomości w `client → server` direction gdy disconnected (max 100 messages)
>
> 10. **Config Panel UI**
>     - Sekcje: Audio (mic/speaker/volume), Avatar (VRM file picker, scale, opacity, position), Persona (dropdown), Observer (interval, enable per game), Hotkeys, Advanced (debug mode, model paths)
>     - Save: `PUT /config` na każdą zmianę (debounce 500ms)
>     - Hot-reload: konfiguracja `audio.*` może wymagać restartu mikrofonu — info w UI
>     - File picker dla VRM: `dialog.showOpenDialog` z filterem `.vrm`
>
> 11. **Setup Wizard (First-Run)**
>     - 6 kroków z PRD_05:
>       1. Welcome
>       2. Check dependencies (LM Studio, Python, models)
>       3. Audio devices selection
>       4. Avatar selection (default vs custom)
>       5. Persona selection (default vs custom)
>       6. Test voice ("Powiedz coś" → STT → LLM → TTS)
>     - Marker: `config/setup_complete.flag`
>
> 12. **Drag & Drop Avatar Position**
>     - Mouse down on canvas → entering "drag mode" (or specific drag handle widget)
>     - Move window via Electron's `setBounds`
>     - Save position to config
>
> 13. **Always-on-Top + Click-through Toggle**
>     - Domyślnie: AOT on, click-through OFF
>     - Komenda voice "Idź na bok" / "Pozwól mi klikać" → click-through ON, awatar nie blokuje
>
> 14. **Build & Distribution**
>     - `electron-builder`: nsis installer Windows
>     - Code signing? (opcjonalne dla solo-dev)
>     - Auto-update: WYŁĄCZONE (manual updates per PRD)
>
> 15. **Performance**
>     - GPU usage frontend: docelowo <2% (rendering 1 modelu, 60fps)
>     - Memory: <300MB process renderer
>     - Profilowanie: Chrome DevTools Performance tab
>
> 16. **Accessibility**
>     - Keyboard navigation w Config Panel
>     - Wystarczające kontrasty kolorów (WCAG AA)
>     - Screen reader friendly (aria-labels)

**Akceptacja:** Frontend developer ma file-by-file plan. VRM loading + emotion + lip-sync deterministic.

**Pytania do użytkownika przed promptem:**

> ❓ **Dla użytkownika przed wygenerowaniem DOK-12:**
> 1. Czy chcesz click-through toggle jako komendę głosową, czy tylko jako hotkey/UI button?
> 2. Czy panel konfiguracji ma być modal poverlay'owany na avatar window, czy osobne okno?
> 3. Setup wizard: w którym kroku ma być pobranie modeli (jeśli brak)? Background download czy blocking?

---

## DOK-13: TEST_PLAN.md — Plan Testowania

**Po co:** PRD_06 ma sekcję testów, ale to high-level. Potrzebny: kompletny rejestr przypadków testowych, struktura katalogów testów, fixtures, CI roadmap (nawet jeśli local).

**Materiały źródłowe:**
- PRD_06_IMPLEMENTATION.md (sekcja Strategia Testowania)
- Wszystkie poprzednie DOK (każdy ma "Test Cases" w swojej sekcji)

**Prompt:**

> Wygeneruj `TEST_PLAN.md` — kompletny plan testowania projektu Assystent. Konsoliduj test cases z poprzednich dokumentów + dodaj brakujące.
>
> Sekcje:
>
> 1. **Pyramid testów**
>    - Unit (~80% testów) — pojedyncze funkcje, klasy, z mockami
>    - Integration (~15%) — orkiestrator z mockowanymi adapterami
>    - Smoke/E2E (~5%) — z realnym LM Studio (manual lub `@pytest.mark.slow`)
>
> 2. **Struktura katalogu** `backend/tests/`
>    ```
>    tests/
>    ├── conftest.py                # fixtures globalne
>    ├── mocks/                     # MockLLMClient, MockSTTEngine, ...
>    │   ├── llm.py
>    │   ├── stt.py
>    │   ├── tts.py
>    │   ├── vlm.py
>    │   └── mcp.py
>    ├── fixtures/                  # przykładowe dane
>    │   ├── audio/                 # *.wav
>    │   ├── images/                # *.png z gier
>    │   ├── transcriptions/
>    │   └── prompts/
>    ├── unit/
>    │   ├── core/                  # orchestrator, prompt_builder, emotion_parser, command_matcher
>    │   ├── ai/                    # adaptery
>    │   ├── mcp/
>    │   ├── memory/
>    │   ├── observer/
>    │   └── config/
>    └── integration/
>        ├── test_voice_pipeline.py # full pipeline z mocks
>        ├── test_observer_loop.py
>        ├── test_session_lifecycle.py
>        └── test_real_llm.py       # @pytest.mark.slow
>    ```
>
> 3. **Fixtures (conftest.py)**
>    - `temp_content_root` — tmpdir + struktura katalogów
>    - `in_memory_db` — SQLite `:memory:` z migracjami
>    - `ephemeral_chroma` — `chromadb.EphemeralClient`
>    - `mock_llm_client` — predefined responses
>    - `sample_session` — session z 20 messages (10 user + 10 assistant)
>    - `sample_player_profile` — PoE2 + Stellaris configured
>    - `mock_websocket` — pytest-websocket dla frontend tests
>
> 4. **Rejestr przypadków testowych**
>    Konsoliduj testy z DOK-05/06/07/08/09/10/11 + dodaj:
>    
>    | Kategoria | Min liczba testów | Coverage target |
>    |-----------|-------------------|-----------------|
>    | emotion_parser | 15 | 100% |
>    | command_matcher | 25 | 95% |
>    | prompt_builder | 12 | 90% |
>    | circuit_breaker | 10 | 100% |
>    | gpu_scheduler | 8 | 90% |
>    | mcp_cache | 12 | 95% |
>    | rate_limiter | 8 | 100% |
>    | session_watchdog | 6 | 85% |
>    | game_detector | 10 | 90% |
>    | observer_loop | 12 | 85% |
>    | repositories (każdy) | 8 | 90% |
>    | config_loader | 15 | 95% |
>    | mcp tools (każde) | 6 | 85% |
>    
>    + **łącznie min ~180 unit testów**
>
> 5. **Integration test scenarios**
>    1. Full voice pipeline: fake audio → MockSTT → MockLLM (returns text+emotion+toolcall) → MockMCP → MockTTS → assert audio + emotion event
>    2. Observer loop: fake screenshot → MockVLM → MockLLM → MockTTS → assert message saved + emotion event
>    3. Session lifecycle: start → 5 interactions → stop → verify DB state
>    4. Hibernation recovery: simulate time skip → assert SessionWatchdog actions
>    5. Circuit breaker: simulate 3 LM Studio failures → assert state OPEN → wait 30s → success → CLOSED
>    6. Persona change: hot-reload → assert prompt rebuild
>    7. Cache hit/miss: web_search 2x → second is cached
>    8. Rate limit: 11 web_search calls → 11. fails → emit emotion
>    9. ChromaDB rotation: insert 10001 messages → assert 100 oldest deleted from chroma + null in sqlite
>    10. Daily check: first startup → background runs → notification in next session
>
> 6. **Smoke tests** (real LM Studio)
>    - `test_lm_studio_connection` — ping
>    - `test_simple_completion` — "Powiedz ok" → response contains "ok"
>    - `test_function_calling` — calculator tool wywołane przez LLM
>    - Marked `@pytest.mark.slow` + skip jeśli LM Studio offline
>
> 7. **Performance tests** (manual semi-automated)
>    - `test_voice_latency` — STT/LLM/TTS sub-metryki, 10 iteracji, p95 reporting
>    - `test_observer_fps_impact` — script: launch game (manual), measure FPS bez/z asystentem (przez OBS log lub PresentMon), assert delta < 5%
>    - `test_vram_budget` — uruchom wszystkie komponenty, pomiar `nvidia-smi`, assert <4GB asystenta
>    - `test_startup_time` — `time python main.py` → <15s
>
> 8. **Frontend tests** (sekcja krótsza, sygnalna)
>    - Unit: Jest + React Testing Library (komponenty, hooks)
>    - E2E: Playwright (start app, sprawdź widoczność awatara, kliknij settings) — opcjonalne
>
> 9. **Coverage tooling**
>    - `pytest --cov=backend --cov-report=html --cov-report=term`
>    - Threshold: fail jeśli < 80% globalnie
>    - Report w `htmlcov/`
>
> 10. **CI/CD**
>     - Lokalny: pre-commit hook → ruff + mypy + pytest unit (fast)
>     - Brak GitHub Actions w MVP (solo-dev, lokalne) — można dodać później
>     - Manual smoke przed każdym kamieniem milowym
>
> 11. **Test data management**
>     - Sample audio: 5 PL utterances, 2 EN, 1 hałas
>     - Sample game screenshots: 5 PoE2, 5 Stellaris (różne sceny)
>     - Disclaimer: nie commituj zrzutów z UI gier (copyright?) — użyj generic stocks lub placeholder
>
> 12. **Definition of "Test Done"**
>     - Każdy moduł ma test happy path + min 2 edge cases + 1 error case
>     - Coverage > 80%
>     - Wszystkie integration scenarios przechodzą
>     - Performance baseline ustalony i powtarzalny

**Akceptacja:** ~180 unit testów + 10 integration. Repo gotowe na `pytest` w 1 komendzie. Coverage report działa.

---

## DOK-14: DEFINITION_OF_DONE.md — Kryteria Akceptacji per Kamień Milowy

**Po co:** PRD_06 ma DoD na wysokim poziomie. Programista potrzebuje checklist `[ ]` które można odhaczać.

**Materiały źródłowe:**
- PRD_06_IMPLEMENTATION.md (Definition of Done section)
- Wszystkie poprzednie DOK (akceptacja każdego)

**Prompt:**

> Wygeneruj `DEFINITION_OF_DONE.md` — kompletne checklisty dla każdej fazy projektu Assystent. To dokument operacyjny — programista odhacza po wykonaniu.
>
> Struktura:
>
> Dla **każdej z 3 faz** (MVP-1, MVP-2, Release):
>
> **A) Functional checklist** — co musi działać end-to-end
>    Format: `- [ ] [ID] Description (verified by: test_name)`
>    Min 30 itemów per faza.
>
> **B) Non-functional checklist** — performance, sandbox, error handling
>    Min 10 itemów.
>
> **C) Documentation checklist**
>    - [ ] README aktualne
>    - [ ] CHANGELOG.md zaktualizowany
>    - [ ] Wszystkie config keys mają dokumentację
>    - [ ] OpenAPI YAML wygenerowany z FastAPI
>    - [ ] User guide dla nowych funkcji
>
> **D) Quality checklist**
>    - [ ] Wszystkie testy przechodzą
>    - [ ] Coverage > 80%
>    - [ ] Linter clean (ruff)
>    - [ ] Type check clean (mypy strict)
>    - [ ] Brak `TODO` w krytycznych modułach
>
> **E) UX checklist**
>    - [ ] Każdy error ma user-facing message (głos lub UI)
>    - [ ] Każdy stan systemu ma wizualizację
>    - [ ] First-run experience tested
>
> **F) Demo scenarios** — lista scenariuszy które musisz móc zademonstrować
>    Faza 1:
>    - [ ] Demo: PTT → "Jaki jest czas?" → odpowiedź głosowa <3s
>    - [ ] Demo: Wakeword → "Jak działa fotosynteza?" → odpowiedź
>    - [ ] Demo: "Idź spać" → awatar znika (nie ma w MVP-1, więc terminal silent) → "Obudź się"
>    - [ ] Demo: LM Studio offline → emotion sad + komunikat
>    Faza 2:
>    - [ ] Demo: Uruchom PoE2 → "Zacznij obserwować" → autonomous comments co 5s
>    - [ ] Demo: "Co widzisz na ekranie?" (na wiki page) → kontekstowy opis
>    - [ ] Demo: "Porównaj LA vs TS build" → web_search + generate_document → plik HTML
>    - [ ] Demo: Restart aplikacji → assistant pamięta ostatnią rozmowę
>    Faza 3:
>    - [ ] Demo: Awatar widoczny nad PoE2 fullscreen-borderless
>    - [ ] Demo: Każda z 16 emocji wywołana przez specific input
>    - [ ] Demo: Lip-sync wizualnie correct
>    - [ ] Demo: Pełen setup wizard od zera
>
> **G) Pre-release checklist** (tylko Release)
>    - [ ] Backup mechanizm działający
>    - [ ] Restore tested
>    - [ ] Wszystkie wpisy do `c:\ai\asystent\` w whitelist (sandbox audit)
>    - [ ] Performance baseline udokumentowany
>    - [ ] Crash recovery tested (kill -9 → restart → resume_after_crash)
>
> **H) Acceptance gate**
>    Per faza: lista 5-7 manual demos które MUSZĄ przejść przed przejściem do następnej fazy. Bez automatyzacji.

**Akceptacja:** ~150 odhaczalnych itemów łącznie. Programista wie kiedy "skończone".

---

## DOK-15: RISK_REGISTER.md — Rozszerzony Rejestr Ryzyk

**Po co:** PRD_06 ma 10 ryzyk wysokopoziomowo. Real risk register potrzebuje: probability×impact, owner, monitoring metrics, response playbook.

**Materiały źródłowe:**
- PRD_06_IMPLEMENTATION.md (sekcja Ryzyka)
- Wszystkie poprzednie DOK (każdy może wskazywać nowe ryzyka)

**Prompt:**

> Wygeneruj `RISK_REGISTER.md` — pełny rejestr ryzyk projektu Assystent.
>
> Format per ryzyko:
>
> ```
> ## R01: VRAM exhaustion przy graniu w wymagającą grę
> 
> ### Klasyfikacja
> - Kategoria: Performance / Resource
> - Probability: Średnia (3/5)
> - Impact: Wysoki (4/5)
> - Risk Score: 12 (P × I)
> - Owner: solo-dev
> 
> ### Opis
> RTX 5090 ma 32GB VRAM. Po starcie: gra (8GB) + LLM (16GB) + VLM (1.5GB) + STT (1GB) + TTS (0.5GB) = 27GB. Brak buforu na peak loady (np. tekstury Stellaris lategame).
> 
> ### Symptomy do monitorowania
> - `nvidia-smi` VRAM > 28GB
> - CUDA OOM error w log
> - User reports: "asystent zwolnił" lub crash
> 
> ### Mitigations (proaktywne)
> 1. Default lekkie modele (Piper + Moondream2)
> 2. GPU Scheduler — sequential inference
> 3. VRAM monitor task (co 30s) → ostrzeżenie przy >90%
> 4. Konfiguracja: `dynamic_vlm_unload: true` — wyładuj VLM gdy nie używany
> 
> ### Response playbook (gdy się zmaterializuje)
> 1. Detect OOM → emit emotion `nervous`, voice: "Mam problem z pamięcią karty"
> 2. Auto-action: VLM unload, observer pause
> 3. Notify user: "Wyłączyłem obserwator. Zamknij coś lub zmień model VLM."
> 4. Recovery: po 60s → próba reload VLM jeśli VRAM <20GB
> 
> ### KPI / Acceptance threshold
> - 0 CUDA OOM errors w 10h gameplaya (test akceptacyjny)
> - VRAM peak < 30GB w 95-tym percentylu
> 
> ### Status
> - [ ] Zidentyfikowane: TAK
> - [ ] Mitigation zaimplementowana: NIE (Faza 1)
> - [ ] Monitoring działa: NIE
> - [ ] Test playbook: NIE
> 
> ### Powiązane ryzyka
> R02 (Latency), R10 (Complexity creep)
> ```
>
> Wygeneruj **min 20 ryzyk**, kategorie:
> - Resource (VRAM, CPU, RAM, dysk)
> - Performance (latency, FPS impact)
> - Stability (crash, hang, deadlock)
> - Compatibility (gra/anti-cheat, Windows version, GPU driver)
> - Security/Privacy (sandbox break, data leak — internet?, PII w logs)
> - UX (sketchy speech recognition, awatar przeszkadza w grze, false positives commands)
> - Integration (LM Studio API change, model deprecation, library breaking change)
> - Project (scope creep, complexity, solo-dev burnout, time slipping)
> - Data (DB corruption, ChromaDB index corruption, config corruption)
> - External (DuckDuckGo blocks, websites change structure for scraper)
>
> Sekcje dodatkowe:
>
> A. **Risk Matrix** — wizualna 5x5 matryca z plotted risks
>
> B. **Top 5 risks** — focus areas dla solo-dev
>
> C. **Risk review schedule** — kiedy re-evaluate (co kamień milowy + przy zmianie scope)
>
> D. **Risk response strategies summary** — accept / mitigate / transfer / avoid (per risk)

**Akceptacja:** Min 20 ryzyk. Top 5 ma pełen playbook. Każde ma KPI.

---

## DOK-16: IMPLEMENTATION_ROADMAP.md — Roadmapa Tygodniowa

**Po co:** Spina wszystko w plan dni/tygodni. PRD_06 podaje "Tydzień 1-4" hasłami. Tu: konkretne tasks per dzień.

**Materiały źródłowe:**
- Wszystkie poprzednie dokumenty (synteza)

**Prompt:**

> Wygeneruj `IMPLEMENTATION_ROADMAP.md` — plan tygodniowy implementacji projektu Assystent. Synteza wszystkich poprzednich dokumentów.
>
> Struktura: **14 tygodni**, każdy z osobną sekcją.
>
> Format per tydzień:
>
> ```
> # Tydzień 3: Orkiestrator i Komendy
> 
> ## Cel tygodnia
> Zbudować orkiestrator AI łączący STT, LLM, TTS + system komend systemowych.
> 
> ## Zadania (5 dni roboczych)
> 
> ### Dzień 1 (poniedziałek): Prompt Builder
> - [ ] Implement `PromptBuilder` class (zgodnie z DOK-05)
> - [ ] Unit tests: 12 cases
> - [ ] Integration: prompt budowany z mockami persona/game/profile
> - **Coverage target**: 90%
> - **Time estimate**: 6h
> - **Dependencies**: DOK-05, DOK-11
> - **Demo**: print zbudowanego promptu dla 3 scenariuszy
> 
> ### Dzień 2 (wtorek): Emotion Parser
> ...
> 
> ### Dzień 3 (środa): Command Matcher
> ...
> 
> ### Dzień 4 (czwartek): Orkiestrator Integration
> ...
> 
> ### Dzień 5 (piątek): End-to-end test + buffer
> - [ ] Integration test: voice input → response
> - [ ] Bug fixes
> - [ ] Code review (self)
> - [ ] Update README + CHANGELOG
> 
> ## Definition of Done — tydzień 3
> - [ ] PromptBuilder, EmotionParser, CommandMatcher: gotowe + testy
> - [ ] Orkiestrator łączy wszystko
> - [ ] Demo: full voice interaction z mockami
> 
> ## Ryzyka tygodnia
> - LLM zwraca tagi w innym formacie niż oczekiwany → robust parser
> 
> ## Następny tydzień
> Tydzień 4: Performance baseline + testy
> ```
>
> **Wszystkie 14 tygodni:**
>
> Faza 1 (Tygodnie 1-4):
> 1. Setup + Interfaces + Config Loader
> 2. STT + TTS + LM Studio Client
> 3. Orkiestrator + Komendy (jak wyżej)
> 4. Performance baseline + testy + buffer
>
> Faza 2 (Tygodnie 5-8):
> 5. DXcam + VLM + OCR
> 6. Observer + Game Profiles + Game Detector
> 7. MCP Tools + Cache + Rate Limiter
> 8. Memory + ChromaDB + Player Profile + Documents
>
> Faza 3 (Tygodnie 9-14):
> 9. Electron + React skeleton
> 10. Three.js + VRM loading + idle animations
> 11. Emocje (16 stanów) — blendshapes + aura
> 12. Lip-sync + body procedural animations
> 13. Config Panel + Setup Wizard + System Tray
> 14. Polish + bug bash + release
>
> Per tydzień: 5 dni × ~6h = 30h. Per dzień: 3-5 zadań, każde z time estimate.
>
> Sekcje globalne:
>
> A. **Buffer rules** — każdy tydzień ma 20% buffer (Piątek po południu)
>
> B. **Milestones** — 3 główne (po każdej fazie) + acceptance gates z DOK-14
>
> C. **Critical path** — które zadania blokują kolejne (graf zależności)
>
> D. **What if slipping?** — playbook przyspieszania (cut scope: które MoSCoW Could/Should można odpuścić)
>
> E. **Daily routine** — sugestia: 9:00 standup z sobą (review wczoraj, plan dzisiaj), 17:00 commit + dziennik

**Akceptacja:** ~14 × 5 = 70 dni roboczych z konkretami. Każdy dzień ma definition of done.

---

# Podsumowanie Procesu

## Etapy

| Etap | Co robisz | Output |
|------|-----------|--------|
| **0. Pre-flight** | Czytasz ten plan, odpowiadasz na pytania z sekcji "Pytania do użytkownika" | `DECISIONS_LOG.md` ✅ **GOTOWE** |
| **1. Sesja DOK-01** | Czyste konto LLM, prompt z DOK-01, dołącz **PRD + DB_SCHEMA + DECISIONS_LOG** | `GLOSSARY.md` |
| **2. Review DOK-01** | Czytasz, uzupełniasz brakujące terminy (5-15 min) | Glossary v1.0 |
| **3. Sesja DOK-02** | Czyste konto LLM, prompt + **wszystkie powyższe + DECISIONS_LOG** | `ENV_SETUP.md` |
| ... | ... powtarzasz dla DOK-03 do DOK-16, zawsze załączając DECISIONS_LOG | ... |
| **17. Final review** | Spójność dokumentów (cross-references), aktualizacja DECISIONS_LOG jeśli nowe decyzje | Komplet docs |

> **Aktualizacja DECISIONS_LOG:** Jeśli w trakcie generowania któregoś z DOK pojawi się nowa decyzja projektowa (np. wybór konkretnej biblioteki, format pliku, próg numeryczny), **dopisz ją do DECISIONS_LOG** zanim przejdziesz do kolejnego dokumentu. Tak utrzymujesz single source of truth.

## Szacunkowy czas

| Aktywność | Czas |
|-----------|------|
| Generowanie 1 dokumentu (LLM) | 5-15 min |
| Review + edycja (user) | 20-60 min per dok |
| Pytania uzupełniające + iteracja | 15-30 min per dok |
| **Per dokument średnio** | **~60 min** |
| **Łącznie 16 dokumentów** | **~16h pracy** |

> Możesz robić po 2-3 dokumenty dziennie i mieć komplet w tydzień.

## Zalecenia

1. **Nie pomijaj kolejności** — DOK-04 (API_CONTRACT) zależy od DOK-03 (CONFIG_SPEC), itd.
2. **Każdy dokument w nowej sesji LLM** — czysty kontekst → spójniejsze wyniki niż dokładanie do długiego wątku.
3. **Załączaj poprzednie dokumenty** — gdy robisz DOK-08 (algorytmy), załącz DOK-04, DOK-05, DOK-06.
4. **Po DOK-08 zrób mid-review** — to środek planu, dobry moment na sanity check spójności.
5. **DOK-16 (Roadmap) na końcu** — bo wymaga wszystkich poprzednich do realnej estymacji.
6. **Aktualizuj DOK-01 (GLOSSARY)** — gdy w kolejnych dokumentach pojawiają się nowe terminy, dopisuj do słownika.

## Kiedy zacząć implementację

Możesz zacząć Fazę 1 implementacji **po DOK-08** (mając: glossary, env, config, API, prompts, emocje, komendy, algorytmy). Pozostałe (DOK-09 do DOK-16) możesz tworzyć równolegle z kodem Fazy 1.

**Minimum viable docs przed kodowaniem: DOK-01, DOK-02, DOK-03, DOK-04, DOK-05, DOK-08, DOK-13, DOK-14, DOK-16.**

DOK-06, 07, 09, 10, 11, 12, 15 mogą być dopisywane "just in time" przed odpowiednim tygodniem implementacji.

---

*Plan v1.1 — 2026-04-27 (z DECISIONS_LOG po sesji decyzyjnej)*
