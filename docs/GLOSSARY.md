# GLOSSARY — Słownik Pojęć Projektu Assystent

> **Status:** v1.0
> **Data:** 2026-04-28
> **Zakres:** Terminy techniczne i domenowe wyciągnięte z PRD (01–06) oraz DB_SCHEMA.md
> **Cel:** Jeden, uzgodniony słownik dla kodu, dokumentacji i UI. Wszystkie nowe pliki muszą używać terminów stąd.

---

## Spis kategorii

1. [Stany systemu](#1-stany-systemu)
2. [Komponenty AI](#2-komponenty-ai)
3. [Pamięć i persystencja](#3-pamięć-i-persystencja)
4. [Obserwator](#4-obserwator)
5. [MCP Tools](#5-mcp-tools)
6. [Awatar](#6-awatar)
7. [Audio](#7-audio)
8. [Domena gier](#8-domena-gier)
9. [Mapowanie EN → PL dla UI](#9-mapowanie-en--pl-dla-ui)

---

## 1. Stany systemu

Dwie ortogonalne osie stanów: **stan zdrowia** (Healthy/Degraded/Minimal — odzwierciedla dostępność komponentów) oraz **stan operacyjny** (Idle/Observer Active/Conversation Lock/Sleep — odzwierciedla co asystent aktualnie robi). Te dwie osie są niezależne — np. można być w `Observer Active` × `Degraded` (obserwator zatrzymany, ale awatar widoczny).

### Healthy / Stan zdrowy 🟢
- **Definicja:** Stan zdrowia systemu, w którym wszystkie komponenty (LLM, STT, TTS, VLM, mikrofon) są dostępne i pełna funkcjonalność jest aktywna.
- **Użycie w kodzie:** `enum HealthState.HEALTHY`, kolumna `sessions.health_state = 'healthy'`, klucz `system_state.health_state`
- **Użycie w UI:** Zielona kropka statusu, brak komunikatu degradacji. W panelu Status: „🟢 Zdrowy".
- **Synonimy do unikania:** „OK", „działa", „normalny" (wieloznaczne); używaj zawsze terminu **Healthy / Zdrowy**.

### Degraded / Stan zdegradowany 🟡
- **Definicja:** Stan zdrowia, w którym LM Studio jest niedostępne (Circuit Breaker w stanie OPEN). Awatar widoczny z emocją `sad`, PTT/wakeword aktywne, obserwator zatrzymany.
- **Użycie w kodzie:** `enum HealthState.DEGRADED`, `sessions.health_state = 'degraded'`
- **Użycie w UI:** Żółta poświata wokół awatara + emocja `sad` + statusowa kropka. Komunikat: „Nie mogę teraz myśleć, LM Studio wyłączone".
- **Synonimy do unikania:** „częściowy błąd", „warning state", „LM offline" (to przyczyna, nie stan).

### Minimal / Tryb minimalny 🔴
- **Definicja:** Stan zdrowia po krytycznym błędzie (brak GPU, crash kluczowych komponentów). Działa tylko awatar i system tray.
- **Użycie w kodzie:** `enum HealthState.MINIMAL`, `sessions.health_state = 'minimal'`
- **Użycie w UI:** Awatar + system tray + komunikat „Oczekuję na zasoby…". Czerwona poświata.
- **Synonimy do unikania:** „awaria", „crash mode", „safe mode" (mylące skojarzenia z Windows).

### Idle / Tryb gotowości
- **Definicja:** Stan operacyjny — asystent czeka na interakcję, odpowiada na pytania ogólne. Obserwator wyłączony. PTT i wakeword aktywne.
- **Użycie w kodzie:** `enum OperationalState.IDLE`
- **Użycie w UI:** Normalne animacje idle awatara (mruganie, oddychanie). Brak dodatkowego wskaźnika.
- **Synonimy do unikania:** „bezczynny", „śpiący" (to jest **Sleep**), „passive" (to jest poziom proaktywności).

### Observer Active / Obserwator aktywny
- **Definicja:** Stan operacyjny — działa pętla obserwatora w tle plus pełna funkcjonalność Idle. Wymaga wykrytego procesu gry.
- **Użycie w kodzie:** `enum OperationalState.OBSERVER_ACTIVE`, `class ObserverLoop`
- **Użycie w UI:** Wskaźnik aktywności obserwatora w panelu Status (np. „👁️ Obserwuje: Path of Exile 2").
- **Synonimy do unikania:** „tryb obserwatora" ≠ „monitorowanie" (ogólne); „watching" (zarezerwowane dla event names); „spying" (negatywne konotacje).

### Conversation Lock / Blokada rozmowy
- **Definicja:** Stan operacyjny — użytkownik aktywnie rozmawia. Pętla obserwatora wstrzymana, audio ducking aktywny dla TTS, priorytet ma odpowiedź użytkownikowi.
- **Użycie w kodzie:** `enum OperationalState.CONVERSATION_LOCK`
- **Użycie w UI:** Zielona poświata (Listening) lub jaśniejszy awatar (Speaking). Brak osobnej etykiety — implicit z animacji.
- **Synonimy do unikania:** „rozmowa w toku", „talking" (zbyt ogólne); „mute observer" (to skutek, nie stan).

### Sleep / Tryb uśpienia
- **Definicja:** Stan operacyjny po komendzie „Idź spać". Awatar ukryty, obserwator zatrzymany, **tylko wakeword** aktywny do wybudzenia.
- **Użycie w kodzie:** `enum OperationalState.SLEEP`
- **Użycie w UI:** Awatar niewidoczny. Ikona w system tray pokazuje stan uśpienia.
- **Synonimy do unikania:** „hidden" (to inny mechanizm — `Ctrl+Shift+A` toggle widoczności, backend nie zmienia stanu); „pauza" (zbyt ogólne); „off" (nieprawda — wakeword działa).

### Crashed / Awaria
- **Definicja:** Stan końcowy sesji wykryty przy starcie backendu — sesja z `ended_at IS NULL` z poprzedniego procesu. Wymusza crash recovery przy starcie.
- **Użycie w kodzie:** `sessions.health_state = 'crashed'`, `def startup_cleanup()`
- **Użycie w UI:** Niewidoczny dla użytkownika; logowany. Opcjonalnie: „Poprzednia sesja zakończyła się nieoczekiwanie".
- **Synonimy do unikania:** „crash" (anglicyzm w kodzie OK, ale w UI używaj **Awaria**); „dead" (konotacje).

### Resumed After Hibernate / Wznowiony po hibernacji
- **Definicja:** Stan sesji wykryty przez `SessionWatchdog` po skoku czasu >30s (hibernacja Windows). Wymusza reconnect WebSocket, ping LM Studio, reinicjalizację mikrofonu.
- **Użycie w kodzie:** `sessions.health_state = 'resumed_after_hibernate'`, `class SessionWatchdog`
- **Użycie w UI:** Awatar: emocja `confused` → `happy`, komunikat „O, wróciłeś!"
- **Synonimy do unikania:** „wake from sleep" (myli się z **Sleep** state); „reconnect".

### Circuit Breaker / Wyłącznik bezpieczeństwa
- **Definicja:** Wzorzec architektoniczny chroniący przed kaskadowymi błędami LM Studio. Stany: `CLOSED` (działa), `OPEN` (przerwany po 3 błędach), `HALF_OPEN` (testowe wywołanie po 30s).
- **Użycie w kodzie:** `class CircuitBreaker`, `enum CircuitState.{CLOSED,OPEN,HALF_OPEN}`, `system_state.circuit_breaker_state`
- **Użycie w UI:** Niewidoczny bezpośrednio. Skutkuje przejściem w stan **Degraded**.
- **Synonimy do unikania:** „retry logic" (to inny wzorzec); „failover" (to inny wzorzec).

---

## 2. Komponenty AI

### LLM (Large Language Model)
- **Definicja:** Duży model językowy odpowiedzialny za rozumowanie i generowanie odpowiedzi. Domyślnie **Gemma 4 E4B** uruchamiany przez **LM Studio** (OpenAI-compatible API).
- **Użycie w kodzie:** `class BaseLLMClient`, `class LMStudioClient`, `config.ai.default_model: "gemma-4-e4b"`
- **Użycie w UI:** „Model językowy" lub po prostu „LLM" w panelu Status. Nazwa konkretnego modelu pokazywana w settings.
- **Synonimy do unikania:** „AI" (zbyt szerokie — VLM też jest AI); „GPT" (nazwa własna konkurencji); „chatbot" (nieadekwatne).

### STT (Speech-to-Text)
- **Definicja:** Komponent transkrybujący mowę na tekst. Domyślnie **Faster-Whisper** (CTranslate2). Pracuje z **confidence threshold** (próg pewności).
- **Użycie w kodzie:** `class BaseSTTEngine`, `class FasterWhisperEngine`, `audio_queue` (STT → orkiestrator)
- **Użycie w UI:** „Rozpoznawanie mowy" w settings. Status w trakcie: „Listening" (zielona poświata).
- **Synonimy do unikania:** „voice recognition" (wieloznaczne — mylone z rozpoznawaniem mówcy); „transkrypcja" w kodzie (używaj STT).

### TTS (Text-to-Speech)
- **Definicja:** Komponent syntezujący mowę z tekstu. Domyślnie **Piper** (lekki, niski VRAM); alternatywa **XTTSv2** (klonowanie głosu). Modulowany przez emocje (speed/pitch).
- **Użycie w kodzie:** `class BaseTTSEngine`, `class PiperTTSEngine`, `class XTTSv2Engine`, `response_queue` (LLM → TTS)
- **Użycie w UI:** „Synteza mowy" w settings. Aktywny: lip-sync na awatarze.
- **Synonimy do unikania:** „voice synth", „głos" (zbyt ogólne).

### VLM (Vision-Language Model)
- **Definicja:** Model multimodalny analizujący obrazy z zrzutów ekranu. Domyślnie **Moondream2** (~1.5 GB VRAM); alternatywa **LLaVA** (~4 GB).
- **Użycie w kodzie:** `class BaseVLMAnalyzer`, `class Moondream2Analyzer`, używany w pipeline obserwatora
- **Użycie w UI:** „Analiza obrazu" lub „VLM" w panelu Status. Niewidoczny bezpośrednio dla użytkownika.
- **Synonimy do unikania:** „vision model" (mylące — to nie samo widzenie); „image AI"; „OCR" (to inny komponent).

### OCR (Optical Character Recognition)
- **Definicja:** Komponent ekstrahujący tekst drobnych elementów UI gier (affixy, tiery, DPS, statystyki). Domyślnie **EasyOCR** (CUDA). Działa **dual** z VLM — VLM analizuje scenę, OCR tylko crop tooltipa.
- **Użycie w kodzie:** `class OCREngine`, `class EasyOCRBackend`, używany w `screen_analyzer.py`
- **Użycie w UI:** Niewidoczny — działa wewnętrznie w pipeline obserwatora.
- **Synonimy do unikania:** „rozpoznawanie tekstu" (wieloznaczne — mylone z STT); „text extraction" (zbyt ogólne).

### Wakeword / Słowo wybudzające
- **Definicja:** Słowo aktywujące asystenta w trybie ciągłego nasłuchiwania (np. „Hej Asystent"). Implementowane przez **openWakeWord** (CPU-only). Konfigurowalne.
- **Użycie w kodzie:** `class WakewordDetector`, `config.audio.wakeword: "..."`
- **Użycie w UI:** „Słowo wybudzające" w settings audio. Status aktywny: ikona mikrofonu z kropką.
- **Synonimy do unikania:** „hot word", „wake word" (rozdzielnie), „aktywator" (nieostre); „Alexa-like trigger".

### Function Calling (Tool Use)
- **Definicja:** Mechanizm OpenAI-compatible, dzięki któremu LLM sam decyduje o wywołaniu narzędzia MCP. Każdy tool zdefiniowany jako JSON schema.
- **Użycie w kodzie:** `tools=[...]` w `BaseLLMClient.chat()`, `config.ai.max_tool_calls_per_turn: 5`
- **Użycie w UI:** Niewidoczny bezpośrednio. Pośrednio: animacja `thinking` gdy LLM woła narzędzia.
- **Synonimy do unikania:** „plugins", „skills", „akcje" (zarezerwowane dla custom commands).

### LM Studio
- **Definicja:** Zewnętrzny serwer (OpenAI-compatible REST API), który hostuje LLM. Asystent komunikuje się z nim przez `http://localhost:1234/v1`. **Wymóg twardy** — bez LM Studio system jest **Degraded**.
- **Użycie w kodzie:** `config.ai.lm_studio_url`, monitorowane przez `CircuitBreaker`
- **Użycie w UI:** „Serwer LLM" w panelu Status. Komunikat błędu: „LM Studio wyłączone".
- **Synonimy do unikania:** „backend LLM" (mylące — backend to też nasz proces Python); „local server".

---

## 3. Pamięć i persystencja

Pamięć dzieli się na dwa odrębne systemy: **historia konwersacji** (SQLite, pełny zapis chronologiczny) oraz **pamięć semantyczna** (ChromaDB, embeddingi do recall). Nie wszystkie wiadomości trafiają do pamięci semantycznej — decyduje flaga `include_in_semantic_memory`.

### Sesja / Session
- **Definicja:** Okres między startem a stopem backendu. Granica wyznaczona kolumnami `started_at` / `ended_at`. `ended_at IS NULL` = sesja aktywna. Crash recovery przy starcie zamyka stare aktywne sesje ze stanem `crashed`.
- **Użycie w kodzie:** Tabela `sessions`, `class SessionRepository`, `system_state.active_session_id`
- **Użycie w UI:** „Sesja" w raportach (np. „Podsumuj sesję"). Czas trwania pokazywany w panelu Status.
- **Synonimy do unikania:** „rozmowa" (mylące — sesja może mieć wiele rozmów); „connection" (to WebSocket).

### Snapshot profilu gracza / Player Context Snapshot
- **Definicja:** Zamrożony obraz aktywnej postaci/buildu/ligi w danym momencie, zapisywany do tabeli `player_context_snapshots`. Tworzony przy: `session_start`, `character_change`, `game_detected`. Używany przez prompt builder.
- **Użycie w kodzie:** Tabela `player_context_snapshots`, `class PlayerSnapshotsRepository`, `enum SnapshotTrigger`
- **Użycie w UI:** Niewidoczny bezpośrednio. Pośrednio: kontekst, który asystent „pamięta" w rozmowie.
- **Synonimy do unikania:** „backup profilu" (myli się z **Player Profile Archive**); „dump"; „save state".

### Profil gracza / Player Profile
- **Definicja:** Plik **YAML** (`data/player_profile.yaml`) — single source of truth dla aktywnych postaci, buildów, lig. **YAML** to źródło prawdy; SQLite tylko snapshotuje.
- **Użycie w kodzie:** `class PlayerProfileRepository`, `class PlayerProfile`, plik `data/player_profile.yaml`
- **Użycie w UI:** Edytowany ręcznie przez użytkownika lub komendą „Gram teraz {postacią}". Nie ma osobnego ekranu — zachęta do edycji w YAML.
- **Synonimy do unikania:** „save game" (to nie save'y gier!); „postać" (to jeden z elementów profilu, nie całość).

### Persona
- **Definicja:** Konfigurowalna osobowość asystenta — plik **Markdown** w `personas/` zawierający sekcje: Osobowość, Ton, Ograniczenia. Wpływa na system prompt i proaktywność, **nie** na parametry TTS (te kontroluje emocja).
- **Użycie w kodzie:** `class PersonaLoader`, `config.persona.active`, hot-reload przez `watchdog`, `system_state.current_persona`
- **Użycie w UI:** „Osobowość" w settings (lista plików .md w `personas/`). Komenda: „Zmień personę na {nazwa}".
- **Synonimy do unikania:** „character" (to gra!); „personality" (w kodzie używaj **Persona**); „style" (zbyt ogólne).

### Pamięć semantyczna / Semantic Memory
- **Definicja:** Kolekcja embeddingów w **ChromaDB** (kolekcja `conversations`, limit 10 000, FIFO) używana do **semantic recall** przy budowaniu promptu. Model: `paraphrase-multilingual-MiniLM-L12-v2`.
- **Użycie w kodzie:** `chromadb_client.conversations`, `def semantic_recall()`, `def rotate_if_needed()`, `messages.include_in_semantic_memory`
- **Użycie w UI:** „Pamięć długoterminowa" w panelu Status (licznik). Komenda: „Zapomnij o X".
- **Synonimy do unikania:** „long-term memory" (OK po angielsku, w PL używaj **Pamięć semantyczna**); „vector store" (niski poziom).

### Knowledge Base / Baza wiedzy
- **Definicja:** Kolekcja **ChromaDB** (`knowledge_base`, **bez limitu**) zawierająca chunki plików `.md` z `knowledge/`. Wypełniana m.in. przez **Daily Meta Check**. Osobna od historii konwersacji.
- **Użycie w kodzie:** `chromadb_client.knowledge_base`, `def ingest_knowledge_file()`, katalog `knowledge/`
- **Użycie w UI:** „Baza wiedzy" lub „Wiedza domenowa" w panelu Status.
- **Synonimy do unikania:** „RAG" (to technika, nie obiekt); „documents" (mylące — dokumenty to wygenerowane raporty); „knowledge graph".

### Semantic Recall / Przywołanie semantyczne
- **Definicja:** Operacja: zapytanie tekstem → top-K embeddingów z ChromaDB → wstrzyknięcie do promptu LLM. Domyślnie 3 z `conversations` + 2 z `knowledge_base`.
- **Użycie w kodzie:** `def semantic_recall(query, game, k_conv=3, k_know=2)`
- **Użycie w UI:** Niewidoczny. Skutek: asystent pamięta wcześniejsze rozmowy.
- **Synonimy do unikania:** „search" (wieloznaczne — jest też full-text search FTS5 i web_search); „recall" samo (zbyt ogólne).

### FTS5 (Full-Text Search)
- **Definicja:** Wirtualna tabela SQLite `messages_fts` indeksująca treść wiadomości tekstowo (nie semantycznie). Używana do dosłownego wyszukiwania.
- **Użycie w kodzie:** `CREATE VIRTUAL TABLE messages_fts USING fts5(...)`, triggery synchronizujące
- **Użycie w UI:** Niewidoczne; wsparcie dla przyszłej funkcji wyszukiwania w historii.
- **Synonimy do unikania:** „LIKE search"; mylenie z **Semantic Recall** — to dwa różne mechanizmy.

### Storage Backend / Backend storage
- **Definicja:** Interfejs `StorageBackend` (Strategy Pattern) umożliwiający wymianę bazy: SQLite (domyślnie) → Postgres → GCP Firestore — bez zmian w logice.
- **Użycie w kodzie:** `class StorageBackend(ABC)`, `class SqliteBackend`, `class PostgresBackend`, `config.storage.backend`
- **Użycie w UI:** „Backend bazy" w settings (advanced).
- **Synonimy do unikania:** „database" (to konkretna implementacja); „adapter" (zbyt ogólne).

### Repository Pattern
- **Definicja:** Wzorzec dostępu do danych: jedna klasa `XxxRepository` per agregat (`MessagesRepository`, `SessionsRepository`, `PlayerSnapshotsRepository`...). Izoluje logikę domenową od warstwy DB.
- **Użycie w kodzie:** `backend/db/repositories/*.py`, `class ConversationRepository`
- **Użycie w UI:** Niewidoczny — wzorzec implementacyjny.
- **Synonimy do unikania:** „DAO" (inny wzorzec, choć podobny); „service" (warstwa wyżej).

### Archive / Archiwizacja
- **Definicja:** Dwa różne mechanizmy: (a) **auto-archiwizacja** wiadomości starszych niż 90 dni → kompresja do `.7z` + `messages.archived = TRUE`; (b) **archiwum profilu** po reset sezonu → tabela `player_profile_archives`.
- **Użycie w kodzie:** `messages.archived`, `messages.archived_at`, tabela `player_profile_archives`, `config.storage.archive_days: 90`
- **Użycie w UI:** „Archiwum" w settings. Komenda: „Zrób backup" (to inny mechanizm — pełny zip).
- **Synonimy do unikania:** „delete" (archiwizacja **nie** usuwa); „backup" (to pełny ZIP całego content root).

### Backup / Kopia zapasowa
- **Definicja:** Kompletny ZIP całego content root (`c:\ai\asystent`) → `backups/assystent_backup_YYYYMMDD.zip`. Komenda: „Zrób backup". **Różne od archiwizacji.**
- **Użycie w kodzie:** Akcja `make_backup`, katalog `backups/`
- **Użycie w UI:** Komenda „Zrób backup". Komunikat: „Backup utworzony: …".
- **Synonimy do unikania:** „archive" (to inny mechanizm — patrz wyżej); „export".

### Daily Meta Check / Codzienny check meta
- **Definicja:** Low-priority task uruchamiany przy starcie (jeśli >24h od ostatniego). Wywołuje `web_search` o aktualne buildy/patche, porównuje z buildem gracza, zapisuje do `knowledge/`. Tabela `daily_checks`.
- **Użycie w kodzie:** Tabela `daily_checks`, `class DailyCheckTask`, `config.mcp.daily_check_on_startup`
- **Użycie w UI:** Proaktywny komunikat: „Hej, mam nowości o meta — chcesz posłuchać?". Toggle: „Codzienny check meta" w settings.
- **Synonimy do unikania:** „daily update", „auto-check", „news check" — używaj zawsze pełnej nazwy.

### Reset Sezonowy / Season Reset
- **Definicja:** Wykrycie nowego sezonu (np. PoE2 liga) → asystent **pyta** użytkownika o reset profilu. Stary profil → `player_profile_archives` z `reason = 'season_reset'`. **Nigdy** nie kasuje automatycznie.
- **Użycie w kodzie:** `player_profile_archives.reason = 'season_reset'`
- **Użycie w UI:** Pytanie: „Wygląda na nowy sezon. Chcesz zresetować profil buildu?".
- **Synonimy do unikania:** „wipe" (sugeruje destrukcję); „new league" (specyficzne dla PoE).

### Content Root
- **Definicja:** Główny katalog zawartości użytkownika: `c:\ai\asystent`. **Oddzielnie** od kodu źródłowego (`c:\code\_repos\antigravity\assystent`). Zawiera: `config/`, `models/`, `personas/`, `knowledge/`, `documents/`, `data/`, `logs/`, `backups/`, `templates/`, `debug/`.
- **Użycie w kodzie:** `config.general.content_root`, ścieżka bazowa wszystkich operacji I/O użytkownika
- **Użycie w UI:** „Folder asystenta" w settings. Komenda „Otwórz dokumenty" otwiera `documents/` z content rootu.
- **Synonimy do unikania:** „working directory" (mylące — proces uruchamia się gdzie indziej); „home folder".

---

## 4. Obserwator

Trzy typy obserwacji ekranu różniące się triggerem i charakterem (pętla vs jednorazowy capture). Wszystkie używają tego samego pipeline'u VLM + (opcjonalnie) OCR, ale różny jest sposób ich aktywacji i częstotliwość.

### Game Observer / Obserwator gry
- **Definicja:** Pętla obserwatora aktywna gdy wykryto proces gry **i** użytkownik dał komendę „Zacznij obserwować". Capture → VLM → [OCR jeśli tooltip] → LLM → komentarz TTS. Interwał per profil gry (5s / 10s / 15s).
- **Użycie w kodzie:** `class ObserverLoop`, `class GameObserver`, `enum ObserverType.GAME`
- **Użycie w UI:** „👁️ Obserwuje: {gra}" w panelu Status. Komendy: „Zacznij obserwować" / „Przestań obserwować".
- **Synonimy do unikania:** „auto-comment", „spy mode", „watch loop"; „monitorowanie" — to ogólne pojęcie.

### On-demand Query / Zapytanie ekranowe na żądanie
- **Definicja:** **Jednorazowy** capture wywołany pytaniem użytkownika typu „Co widzisz na ekranie?" / „O czym jest ta strona?". Full screenshot + crop 600×400 wokół kursora. Bez pętli.
- **Użycie w kodzie:** Tool MCP `screen_capture`, `class OnDemandScreenQuery`, `enum ObserverType.ON_DEMAND`
- **Użycie w UI:** Aktywowany pytaniem głosowym; brak osobnego przycisku.
- **Synonimy do unikania:** „screenshot" (wieloznaczne — to też mechanizm zapisu plików w `debug/screenshots/`); „one-shot capture".

### Ambient Observer / Obserwator otoczenia
- **Definicja:** Jak **On-demand Query**, ale **poza grą** (np. przeglądanie wiki). **Wyłączony domyślnie** (`config.observer.ambient_enabled: false`). Jednorazowy capture, brak pętli.
- **Użycie w kodzie:** `enum ObserverType.AMBIENT`, `config.observer.ambient_enabled`
- **Użycie w UI:** Toggle „Obserwator poza grą" w settings (advanced).
- **Synonimy do unikania:** „desktop observer", „passive watch"; **nie myl** z **Game Observer**.

### Game Detector / Detektor gry
- **Definicja:** Komponent automatycznie rozpoznający uruchomioną grę kaskadowo: (1) match nazwy procesu z `process_names` w game profile YAML, (2) fallback **VLM** (rozpoznanie z UI), (3) ręczne nadpisanie. Tabela: `game_detections.detection_method ∈ ('process','vlm','manual')`.
- **Użycie w kodzie:** `class GameDetector`, plik `backend/observer/game_detector.py`, tabela `game_detections`
- **Użycie w UI:** Wykrycie → proaktywny komunikat „O, widzę że odpalasz {gra}…".
- **Synonimy do unikania:** „game recognition" (wieloznaczne); „process scanner" (zbyt techniczne).

### Game Profile / Profil gry
- **Definicja:** Plik **YAML** w `config/game_profiles/{gra}.yaml` opisujący: nazwy procesów, typ obserwatora (`action`/`strategic`), interwał, focus areas, screen regions, context prompt, MCP sources.
- **Użycie w kodzie:** `class GameProfile`, `class GameProfileLoader`, katalog `config/game_profiles/`
- **Użycie w UI:** Edytowany ręcznie. Lista wykrywanych gier wyliczana automatycznie z plików YAML.
- **Synonimy do unikania:** „game config" (zbyt ogólne); „preset"; **nie myl** z **Player Profile** (tu opisujemy grę, tam gracza).

### Observer Loop / Pętla obserwatora
- **Definicja:** Asynchroniczna pętla: `Capture → VLM → [OCR] → LLM → TTS` co N sekund. Wstrzymywana w stanie **Conversation Lock**, anulowana przy aktywacji PTT.
- **Użycie w kodzie:** `class ObserverLoop.run()`, `config.observer.default_interval_seconds`
- **Użycie w UI:** Niewidoczna bezpośrednio; manifestuje się komentarzami i pingiem powiadomienia.
- **Synonimy do unikania:** „polling loop"; „capture loop" (to tylko jeden krok pętli).

### Scene Hash / Hash sceny
- **Definicja:** SHA256 opisu sceny zwróconego przez VLM, zapisywany w `messages.scene_hash` (tylko `source='observer'`). Służy do **deduplikacji** — pomijanie komentarzy o tej samej scenie.
- **Użycie w kodzie:** `messages.scene_hash`, kolumna nullable, używana tylko gdy `source='observer'`
- **Użycie w UI:** Niewidoczny — czysto wewnętrzny mechanizm.
- **Synonimy do unikania:** „screenshot hash" (to nie hash obrazu! to hash tekstu opisu); „dedup key".

### Screen Capture / Zrzut ekranu
- **Definicja:** Pojedynczy zrzut ekranu wykonywany przez **DXcam** (najszybsza metoda na Windows, DirectX). Minimalny wpływ na FPS.
- **Użycie w kodzie:** `class ScreenCapturer`, używa biblioteki `dxcam`
- **Użycie w UI:** Niewidoczne. W `debug/screenshots/` zapisywane przy `config.debug.save_screenshots: true`.
- **Synonimy do unikania:** „screenshot" w kontekście MCP tool — **screen_capture** to nazwa narzędzia; w pozostałych miejscach OK używać „zrzut ekranu".

### Pipeline VLM + OCR (Dual)
- **Definicja:** Dwuścieżkowa analiza: VLM analizuje całą scenę, równolegle OCR wyciąga tekst z cropa tooltipa/itemu (jeśli wykryto). **Oba wyniki** trafiają do LLM jako kontekst.
- **Użycie w kodzie:** `class ScreenAnalyzer.analyze_dual()`
- **Użycie w UI:** Niewidoczne.
- **Synonimy do unikania:** „OCR pipeline" (to tylko połowa); „vision pipeline" (zbyt ogólne).

### Focus Areas
- **Definicja:** Pole w `game_profile.yaml` definiujące co VLM powinien priorytetowo analizować (np. `[builds, loot, combat, boss_mechanics]`). Wstrzykiwane do context prompt.
- **Użycie w kodzie:** `GameProfile.focus_areas: List[str]`
- **Użycie w UI:** Edytowane w YAML.
- **Synonimy do unikania:** „topics", „areas of interest" — w kodzie używaj **focus_areas**.

---

## 5. MCP Tools

**MCP** w tym projekcie odnosi się do **wewnętrznego** systemu function calling (6 narzędzi LLM), nie do zewnętrznego protokołu Model Context Protocol Anthropic. Konwencja nazewnicza została odziedziczona historycznie.

### MCP Tool / Narzędzie MCP
- **Definicja:** Funkcja, którą LLM może wywołać przez **function calling**. Każde narzędzie zdefiniowane jako JSON schema (OpenAI-compatible). Sześć narzędzi: `web_search`, `web_scraper`, `get_current_time`, `calculator`, `generate_document`, `screen_capture`.
- **Użycie w kodzie:** `backend/mcp/*.py`, `class MCPTool(ABC)`, tabela `tool_calls`
- **Użycie w UI:** Niewidoczne bezpośrednio. Animacja `thinking` na awatarze gdy LLM woła narzędzie.
- **Synonimy do unikania:** „plugin", „skill", „API" — używaj **MCP Tool** lub **narzędzie**.

### Tool Call / Wywołanie narzędzia
- **Definicja:** Pojedyncze użycie MCP toola w odpowiedzi na komunikat użytkownika. Zapisywane do `tool_calls` z `turn_sequence` (1–5), `input_json`, `output_json`, `duration_ms`, `success`.
- **Użycie w kodzie:** Tabela `tool_calls`, `class ToolCallsRepository`
- **Użycie w UI:** Niewidoczne; w `/debug/last_interaction` widoczne dla developera.
- **Synonimy do unikania:** „function invocation" (synonim, ale używaj **tool call**); „API call".

### Turn Sequence / Sekwencja w turze
- **Definicja:** Numer kolejnego tool calla w **jednej turze** rozmowy (od 1 do **max 5**, kontrolowane przez `max_tool_calls_per_turn`). Po osiągnięciu limitu LLM odpowiada na bazie zebranych danych. `generate_document` **nie liczy się** do limitu.
- **Użycie w kodzie:** `tool_calls.turn_sequence INTEGER CHECK(turn_sequence BETWEEN 1 AND 5)`, `config.ai.max_tool_calls_per_turn: 5`
- **Użycie w UI:** Niewidoczne. Limit można podnieść w settings (advanced).
- **Synonimy do unikania:** „step" (zbyt ogólne); „iteration".

### Function Calling
- **Definicja:** Patrz sekcja 2 (Komponenty AI). Mechanizm OpenAI-compatible łączący LLM z MCP tools.

### MCP Cache
- **Definicja:** Tabela `mcp_cache` z TTL per typ zapytania: game meta 24h, ogólne 1h, strony (web_scraper) 7 dni. Klucz: `SHA256(tool_name + canonical_json(params))`. Komenda „Odśwież informacje o X" → bypass cache.
- **Użycie w kodzie:** Tabela `mcp_cache`, `class MCPCacheRepository`, `config.mcp.cache_ttl_*`
- **Użycie w UI:** Niewidoczne. Komenda bypassu: „Odśwież informacje o {temat}".
- **Synonimy do unikania:** „response cache" (zbyt ogólne); „query cache".

### Rate Limiter
- **Definicja:** Limit **10 requestów/minutę** dla `web_search`. Po przekroczeniu: emocja `disappointed`, komunikat „Nie mogę teraz szukać, spróbuję później."
- **Użycie w kodzie:** `class RateLimiter`, `config.mcp.web_search_rate_limit: 10`
- **Użycie w UI:** Niewidoczny aż do trafienia limitu.
- **Synonimy do unikania:** „throttle" (synonim); „quota".

### web_search
- **Definicja:** Tool MCP — wyszukiwanie przez **DuckDuckGo / SearXNG** (bez API key, prywatne). Limit: 10 req/min. Cache TTL: 1h ogólne, 24h game meta.
- **Użycie w kodzie:** `backend/mcp/web_search.py`, `class WebSearchTool`
- **Użycie w UI:** Niewidoczne; LLM woła automatycznie.
- **Synonimy do unikania:** „Google search" (nieprawda — używamy DDG/SearXNG); „search engine".

### web_scraper
- **Definicja:** Tool MCP — pobranie i parsowanie URL do tekstu. Cache TTL: 7 dni. **Fallback:** jeśli strona to SPA i scraper nie działa → asystent pyta użytkownika konwersacyjnie.
- **Użycie w kodzie:** `backend/mcp/web_scraper.py`, `class WebScraperTool`
- **Użycie w UI:** Niewidoczne; aktywne np. przy „Importuj build z URL".
- **Synonimy do unikania:** „crawler"; „URL fetcher".

### get_current_time
- **Definicja:** Tool MCP — zwraca `datetime.now()`. Bez limitu, bez cache. Używany m.in. przez logikę **quiet hours**.
- **Użycie w kodzie:** `backend/mcp/time_tool.py`
- **Użycie w UI:** Niewidoczne.
- **Synonimy do unikania:** „clock"; „time API".

### calculator
- **Definicja:** Tool MCP — bezpieczna ewaluacja wyrażeń matematycznych przez **asteval** (nie `eval()`!). Bez limitu.
- **Użycie w kodzie:** `backend/mcp/calculator.py`, biblioteka `asteval`
- **Użycie w UI:** Niewidoczne.
- **Synonimy do unikania:** „math eval"; „expression parser".

### generate_document
- **Definicja:** Tool MCP — generowanie raportów MD/HTML. **Nie liczy się** do `max_tool_calls_per_turn`. Zapisuje do `documents/` i rejestruje w tabeli `generated_documents`.
- **Użycie w kodzie:** `backend/mcp/document_generator.py`, tabela `generated_documents`
- **Użycie w UI:** Komenda „Napisz raport o…", „Podsumuj sesję", „Porównaj buildy…".
- **Synonimy do unikania:** „document creator"; „report generator" (synonim, ale używaj **generate_document** w kodzie).

### screen_capture
- **Definicja:** Tool MCP wywoływany przez LLM dla **on-demand query**. Wewnętrznie używa DXcam + VLM. Bez limitu.
- **Użycie w kodzie:** `backend/mcp/screen_capture.py`
- **Użycie w UI:** Niewidoczne; aktywowane pytaniem o ekran.
- **Synonimy do unikania:** **Nie myl** z `class ScreenCapturer` (komponent niskopoziomowy) ani z mechanizmem **debug screenshots**.

---

## 6. Awatar

### VRM
- **Definicja:** Format pliku 3D dla awatarów humanoidalnych (rozszerzenie GLTF). Standard używany przez `three-vrm` w warstwie frontend (Three.js). Domyślny model dostarczany z aplikacją w `models/avatar/default.vrm` (anime, darmowa licencja).
- **Użycie w kodzie:** `import { VRMLoaderPlugin, VRMHumanoid } from 'three-vrm'`, ścieżka `models/avatar/*.vrm`
- **Użycie w UI:** „Model awatara" w settings — wybór z dropdownu.
- **Synonimy do unikania:** „avatar file" (zbyt ogólne); „3D model" (zbyt ogólne); „VRoid" (to konkretny edytor).

### Blendshape
- **Definicja:** Predefiniowany kształt twarzy w modelu VRM (np. `happy`, `surprised`). Podstawowa warstwa wyrażania emocji. Skanowane przy ładowaniu modelu — niedostępne mapowane na **fallback** (aura/body).
- **Użycie w kodzie:** `vrm.expressionManager.setValue('happy', 1.0)`, scan przy load
- **Użycie w UI:** Niewidoczne — automatyczne mapowanie emocji.
- **Synonimy do unikania:** „morph target" (synonim techniczny GLTF, ale w kontekście VRM używaj **blendshape**); „expression" (mylące — Expression Manager to wyższa abstrakcja).

### Trójwarstwowy Fallback Emocji
- **Definicja:** Hierarchia wyrażania emocji: (1) **Blendshapes VRM** → jeśli model wspiera, (2) **Aura/shader** → kolorowa poświata (zawsze działa), (3) **Body animation** → proceduralne gesty Three.js (rotacje kości, oscylacje). Zapewnia, że emocja jest widoczna **niezależnie** od jakości modelu.
- **Użycie w kodzie:** `class EmotionRenderer.render(emotion, available_blendshapes)`
- **Użycie w UI:** Niewidoczne — automat.
- **Synonimy do unikania:** „emotion stack"; „rendering chain".

### Aura
- **Definicja:** Kolorowa poświata wokół awatara — warstwa 2 trójwarstwowego fallbacka. Niezależna od modelu (działa zawsze). Również wskaźnik **stanów wizualnych systemu** (np. zielona — Listening, czerwona — Error).
- **Użycie w kodzie:** `class AuraShader`, parametry koloru per emocja i per stan
- **Użycie w UI:** Widoczna jako poświata wokół awatara.
- **Synonimy do unikania:** „glow" (ogólne); „halo"; „outline".

### Emocja / Emotion
- **Definicja:** Jeden z **16 stanów emocjonalnych** asystenta. Cztery kategorie: **Pozytywne** (happy, amused, proud, sympathetic), **Negatywne** (sad, disappointed, angry, disgusted), **Energetyczne** (excited, scared, surprised, nervous), **Refleksyjne** (thinking, confused, nostalgic, sarcastic). Każda mapuje się na: blendshape + aura + body animation + modulację TTS (speed/pitch).
- **Użycie w kodzie:** `enum Emotion.{HAPPY,SAD,...}` (16 wartości), kolumna `messages.emotion`, event WebSocket `emotion`
- **Użycie w UI:** Wyświetlana przez awatara. W debug visible jako tag `[EMO:nazwa]`.
- **Synonimy do unikania:** „mood" (zbyt ogólne i mylące — `mood` to też stan długoterminowy w niektórych systemach); „feeling"; „expression" (to tylko warstwa wyrazowa).

### Inline Emotion Tag / Tag emocji w odpowiedzi
- **Definicja:** Marker `[EMO:nazwa]` wstawiany przez LLM w odpowiedź, np. `[EMO:thinking] Hm, ciekawe pytanie…`. Parser wyciąga tag, **usuwa** go z tekstu przed TTS, wysyła emocję przez WebSocket.
- **Użycie w kodzie:** `class EmotionParser.parse(text) -> (cleaned_text, emotion)`, regex `\[EMO:(\w+)\]`
- **Użycie w UI:** Tag **niewidoczny** dla użytkownika — usuwany przed wyświetleniem/TTS.
- **Synonimy do unikania:** „emotion marker"; „tag" samo (zbyt ogólne).

### Stan wizualny systemu / System Visual State
- **Definicja:** Wizualne reprezentacje stanu **operacyjnego** (nie emocji): `Idle`, `Listening`, `Thinking`, `Speaking`, `Error`, `Degraded`. Realizowane głównie przez aurę i animacje.
- **Użycie w kodzie:** `enum VisualState`, event WebSocket `status`
- **Użycie w UI:** Zielona poświata = Listening; pulsująca aura + animacja zamyślenia = Thinking; jaśniejszy awatar + lip-sync = Speaking; czerwona aura + emocja `sad` = Error; żółta aura + statusowa kropka = Degraded.
- **Synonimy do unikania:** „status indicator" (zbyt ogólne); **nie myl** z **emocją** — emocja to ekspresja treści, wizualny stan to ekspresja stanu systemu.

### Lip-sync
- **Definicja:** Synchronizacja ruchu ust awatara z audio TTS. Kontrolowane przez frontend (Three.js) na podstawie **stream audio** odbieranego po WebSocket.
- **Użycie w kodzie:** `class LipSyncController` (frontend), event `audio_stream`
- **Użycie w UI:** Widoczne podczas mowy asystenta. **Wyłączane** w **trybie cichym**.
- **Synonimy do unikania:** „mouth sync"; „phoneme sync".

### Animacje Idle / Idle Animations
- **Definicja:** Subtelne ruchy awatara w stanie spoczynku (mruganie, oddychanie, drobne przesunięcia). Generowane **proceduralnie** w Three.js — bez plików zewnętrznych. Zapewniają, że awatar nigdy nie jest „zamrożony".
- **Użycie w kodzie:** `class IdleAnimator`, sinusoidalne oscylacje na rotacjach kości
- **Użycie w UI:** Domyślne zachowanie awatara w **Idle**.
- **Synonimy do unikania:** „ambient animation" (mylące — **Ambient Observer** to coś innego); „resting".

### Always-on-Top / Awatar zawsze na wierzchu
- **Definicja:** Cecha okna awatara — pozostaje widoczne **nad** wszystkimi innymi oknami (włącznie z grą w trybie borderless). Realizowane przez Electron + frameless window.
- **Użycie w kodzie:** Electron `BrowserWindow({ alwaysOnTop: true, frame: false, transparent: true })`
- **Użycie w UI:** Toggle w settings — przezroczystość konfigurowalna. Hotkey `Ctrl+Shift+A` toggle widoczności.
- **Synonimy do unikania:** „topmost"; „pinned" (mylące).

### Procedural Animations / Animacje proceduralne
- **Definicja:** Animacje generowane **kodem** (Three.js + VRMHumanoid API), nie odtwarzane z plików: rotacje kości (head tilt, body lean), sinusoidalne oscylacje (oddychanie, kołysanie), jednorazowe akcenty (podskoczenie = translate Y + spring-back).
- **Użycie w kodzie:** `class ProceduralAnimator`, użycie `vrm.humanoid.getRawBoneNode(...)`
- **Użycie w UI:** Niewidoczne pod kątem implementacji; widoczne jako żywe ruchy awatara.
- **Synonimy do unikania:** „skeletal animation" (mylące — to też ruch szkieletu, ale z plików); „canned animation" (przeciwieństwo).

---

## 7. Audio

### PTT (Push-to-Talk)
- **Definicja:** Tryb interakcji głosowej — przytrzymanie konfigurowalnego klawisza/przycisku myszy aktywuje nagrywanie, zwolnienie kończy. Zawsze ma **najwyższy priorytet** audio (audio duck < 200ms).
- **Użycie w kodzie:** `class PTTHandler`, `pynput` listeners, `system_state.audio_mode = 'ptt'`
- **Użycie w UI:** „Push-to-Talk" w settings; konfigurowalny klawisz. Aktywne: zielona poświata.
- **Synonimy do unikania:** „push to talk" (rozdzielnie — używaj akronimu **PTT**); „naciśnij i mów" (długie).

### Wakeword
- **Definicja:** Patrz sekcja 2 (Komponenty AI). Słowo wybudzające (np. „Hej Asystent") aktywujące nagrywanie w trybie ciągłego nasłuchiwania. Tryb **alternatywny do PTT**.
- **Użycie w kodzie:** `system_state.audio_mode = 'wakeword'`
- **Użycie w UI:** Toggle „PTT ↔ Wakeword" w settings — switching bez restartu.
- **Synonimy do unikania:** Patrz sekcja 2.

### Audio Duck / Ducking audio
- **Definicja:** Natychmiastowe wyciszenie TTS (głośność → 0% w **<200ms**) gdy użytkownik aktywuje PTT. Komentarz obserwatora może być **anulowany** jeśli w kolejce. Po zakończeniu interakcji obserwator wznawia.
- **Użycie w kodzie:** `class AudioDucker.duck()`, `class AudioPriorityQueue`
- **Użycie w UI:** Niewidoczne — efekt natychmiastowej responsywności.
- **Synonimy do unikania:** „audio fade"; „mute on PTT" (zbyt techniczne); „priority interrupt".

### Tryb cichy / Silent Mode
- **Definicja:** Komenda „Wycisz się" → TTS wyłączony, tekst wyświetlany jako **overlay** obok awatara, lip-sync wyłączony. Przydatne np. na voice chat z innymi graczami. Powrót: „Możesz mówić".
- **Użycie w kodzie:** `system_state.silent_mode = 'TRUE'/'FALSE'`, event WebSocket `text_overlay`. Resetowany przy starcie.
- **Synonimy do unikania:** „mute mode" (mute to wycisz całkiem — tu jest **tekst zamiast głosu**); „text mode"; „quiet mode" (mylące — patrz **Quiet Hours**).

### Quiet Hours / Godziny ciszy
- **Definicja:** Konfigurowalny zakres godzin (domyślnie `["23:00", "07:00"]`) gdy asystent **nie inicjuje** rozmów proaktywnie, a komentarze obserwatora mają obniżoną głośność lub idą jako overlay tekstowy. PTT/wakeword działają normalnie.
- **Użycie w kodzie:** `config.general.quiet_hours`, decyzje oparte o `get_current_time` MCP tool
- **Użycie w UI:** Edytowalne w settings („Godziny ciszy: 23:00 — 07:00").
- **Synonimy do unikania:** „silent mode" (to inny mechanizm — patrz **Tryb cichy**); „do not disturb"; „night mode".

### STT Confidence / Pewność transkrypcji
- **Definicja:** Wartość 0.0–1.0 zwracana przez STT określająca jakość rozpoznania. Trzy progi: **>0.7** normalne przetwarzanie, **0.4–0.7** prośba o potwierdzenie, **<0.4** prośba o powtórzenie + emocja `confused`. Konfigurowalne w `config.audio.stt_confidence_threshold`.
- **Użycie w kodzie:** Kolumna `messages.confidence_score REAL`, `config.audio.stt_confidence_threshold: 0.7`, `config.audio.stt_low_confidence_threshold: 0.4`
- **Użycie w UI:** Niewidoczna jako liczba; manifestuje się komunikatami: „Nie jestem pewien czy dobrze usłyszałem…" / „Przepraszam, nie zrozumiałem".
- **Synonimy do unikania:** „accuracy" (mylące — to inna metryka); „certainty"; „score" (zbyt ogólne).

### Notification Sound / Ping powiadomienia
- **Definicja:** Subtelny dźwięk **przed** komentarzem obserwatora — zapobiega zaskakiwaniu gracza niespodziewanym głosem. Konfigurowalny: `audio.notification_sound: true/false`.
- **Użycie w kodzie:** `config.audio.notification_sound`, plik `assets/notification.wav`
- **Użycie w UI:** Toggle „Ping przed komentarzem" w settings audio.
- **Synonimy do unikania:** „chime"; „alert sound"; „bell".

### TTS Emotion Modulation / Modulacja emocji TTS
- **Definicja:** Dynamiczne dostosowanie **speed** i **pitch** TTS w zależności od emocji (np. `excited` = 1.2× speed, +10% pitch; `sad` = 0.8× speed, −5% pitch). Kontrolowane przez emocję, **nie** przez personę.
- **Użycie w kodzie:** `class TTSEmotionModulator`, parametry per emocja w `config/tts_emotions.yaml`
- **Użycie w UI:** Niewidoczna jako konfiguracja użytkownika (advanced).
- **Synonimy do unikania:** „voice modulation" (zbyt ogólne); „prosody control".

### GPU Scheduler / Scheduler GPU
- **Definicja:** Mutex/semaphore zapewniający, że żadne dwa inference (STT, LLM, TTS, VLM) **nie wykonują się równocześnie** na GPU. Priorytety: 1=STT (mowa userka), 2=LLM (odpowiedź), 3=TTS (CPU możliwe), 4=VLM (obserwator, najniższy).
- **Użycie w kodzie:** `class GPUScheduler`, `asyncio.Semaphore`, plik `backend/core/gpu_scheduler.py`
- **Użycie w UI:** Niewidoczny; manifestuje się responsywnością.
- **Synonimy do unikania:** „GPU lock" (jest częścią mechanizmu, ale nazwa = **scheduler**); „inference queue".

### Heartbeat
- **Definicja:** Ping co **5 sekund** przez WebSocket frontend↔backend. Brak pong przez **15 sekund** → disconnect, auto-reconnect ze sync stanu.
- **Użycie w kodzie:** `class HeartbeatTask`, event WebSocket `ping`/`pong`
- **Użycie w UI:** Niewidoczne — obsługa po stronie infra.
- **Synonimy do unikania:** „keep-alive"; „health check" (to inny mechanizm — `/status` endpoint).

---

## 8. Domena gier

### Build
- **Definicja:** Kompozycja umiejętności, atrybutów i ekwipunku w grach action-RPG (głównie **PoE2**). Pole w `player_profile.yaml` per postać. Importowalny z URL (np. `maxroll.gg`) przez `web_scraper`. Snapshotowany w `player_context_snapshots.build_name`/`build_url`.
- **Użycie w kodzie:** `PlayerProfile.characters[].build`, `player_context_snapshots.build_name`
- **Użycie w UI:** „Build: Lightning Arrow" w panelu profilu. Komenda: „Importuj build z {URL}".
- **Synonimy do unikania:** „setup" (zbyt ogólne); „spec" (D&D-konkretne); „loadout" (FPS-konkretne).

### Liga / League
- **Definicja:** Sezonowy resetowany świat w grach takich jak **PoE2** (np. „Season 2"). Pole w `player_profile.yaml` i `player_context_snapshots.league`. Wykrycie nowej ligi → trigger **Reset Sezonowy**.
- **Użycie w kodzie:** `PlayerProfile.games[*].league`, `player_context_snapshots.league`
- **Użycie w UI:** „Liga: Season 2" w profilu.
- **Synonimy do unikania:** „season" w kodzie (używaj **league** dla PoE konkretnie, **season** w kontekście **Reset Sezonowy** ogólnie).

### Klasa / Character Class
- **Definicja:** Archetyp postaci w grach RPG (np. `Deadeye`, `Marauder`). Pole w `player_profile.yaml` per postać i `player_context_snapshots.character_class`.
- **Użycie w kodzie:** `PlayerProfile.characters[].class`, `player_context_snapshots.character_class`
- **Użycie w UI:** „Klasa: Deadeye" w profilu.
- **Synonimy do unikania:** „role" (MMO-konkretne); „archetype".

### Postać / Character
- **Definicja:** Pojedyncza grywalna postać użytkownika w grze, z imieniem, klasą, buildem, leveluem. Wiele postaci per gra. Aktywna wskazywana przez `active_character`. Komenda: „Gram teraz {postacią}" → zmiana `active_character` + snapshot.
- **Użycie w kodzie:** `PlayerProfile.games[*].characters[]`, `player_context_snapshots.active_character`
- **Użycie w UI:** „Aktywna postać: SparkyBoy". Lista wszystkich w profilu.
- **Synonimy do unikania:** „avatar" (to wygląd asystenta!); „hero"; „toon" (slang).

### Meta
- **Definicja:** Aktualnie najlepsze/popularne buildy, strategie, patche w danej grze. Trackowane przez **Daily Meta Check**. Zapisywane jako pliki .md w `knowledge/{gra}/`.
- **Użycie w kodzie:** `daily_checks.result_summary`, katalog `knowledge/`
- **Użycie w UI:** „Meta": „Hej, mam nowości o meta {gra} — chcesz posłuchać?".
- **Synonimy do unikania:** „trending"; „top builds" (zbyt wąskie — meta to też patche, balance changes).

### Sezon / Season
- **Definicja:** Cykliczny okres w grach live-service (PoE2: liga, Stellaris: brak typowych sezonów). Wykrycie nowego → **Reset Sezonowy** z archiwizacją profilu do `player_profile_archives` z `reason='season_reset'`.
- **Użycie w kodzie:** `player_profile_archives.season`, decyzja w MCP layer
- **Użycie w UI:** „Wygląda na nowy sezon. Chcesz zresetować profil?".
- **Synonimy do unikania:** „league" w kontekście archiwum (używaj `season` w nazwie pola); **nie myl** z `messages.session_id`.

### Affix
- **Definicja:** Modyfikator atrybutu na przedmiocie w grach action-RPG (np. „Adds 45-78 Lightning Damage"). Ekstrahowany przez **OCR** z tooltipów. Charakteryzowany przez **tier** (jakość).
- **Użycie w kodzie:** Wynik `OCREngine.parse_affixes()`, używany przez VLM + LLM
- **Użycie w UI:** Wyświetlany w komentarzach asystenta: „Niezły łuk! Ma T2 flat lightning…".
- **Synonimy do unikania:** „mod" (slang); „bonus" (zbyt ogólne); „stat" (wieloznaczne).

### Tier
- **Definicja:** Stopień jakości affixu — wyższy tier = lepsza wartość statystyki. Notowane jako T1, T2, T3… T1 zwykle najlepszy.
- **Użycie w kodzie:** Pole w wyniku OCR, używane przez LLM do oceny przedmiotu
- **Użycie w UI:** „T2 flat lightning damage".
- **Synonimy do unikania:** „rank" (mylące — różne semantyki w różnych grach); „level" (`postać.level` to coś innego!).

### DPS (Damage Per Second)
- **Definicja:** Metryka obrażeń na sekundę — kluczowa statystyka w grach action-RPG. Ekstrahowana z UI przez OCR.
- **Użycie w kodzie:** Wynik OCR, używane przez LLM w komentarzach
- **Użycie w UI:** „Twój DPS to 250k — wystarczy na T16 mapy".
- **Synonimy do unikania:** „damage" (zbyt ogólne); „output".

### Process Name / Nazwa procesu
- **Definicja:** Nazwa wykonywalnego procesu Windows (np. `PathOfExile_x64.exe`) używana przez **Game Detector** do auto-rozpoznania gry. Lista per profil w `game_profile.yaml.process_names`.
- **Użycie w kodzie:** `GameProfile.process_names: List[str]`, `game_detections.process_name`
- **Użycie w UI:** Edytowane w YAML.
- **Synonimy do unikania:** „executable" (techniczne); „exe" (potoczne).

### Observer Type / Typ obserwatora
- **Definicja:** Pole w `game_profile.yaml` określające charakter gry: `action` (szybkie tempo, krótszy interwał ~5s) lub `strategic` (wolne tempo, dłuższy interwał ~15s).
- **Użycie w kodzie:** `GameProfile.observer_type: 'action' | 'strategic'`, wpływa na `default_interval_seconds`
- **Użycie w UI:** Edytowane w YAML; nie pokazywane bezpośrednio.
- **Synonimy do unikania:** „pace" (zbyt ogólne); „game type" (mylące — to nie genre).

### Active Character
- **Definicja:** Aktualnie używana postać w grze — pole w `player_profile.yaml`. Zmieniane komendą „Gram teraz {postacią}". Każda zmiana → snapshot `player_context_snapshots` z `trigger='character_change'`.
- **Użycie w kodzie:** `PlayerProfile.games[*].active_character: str`, `player_context_snapshots.active_character`, `enum SnapshotTrigger.CHARACTER_CHANGE`
- **Użycie w UI:** Wyświetlana jako „Aktywna: SparkyBoy".
- **Synonimy do unikania:** „current character"; „selected" (mylące).

---

## 9. Mapowanie EN → PL dla UI

Tabela tekstów wyświetlanych użytkownikowi. **Lewa kolumna** to terminy/etykiety techniczne lub angielskie (jak pojawiają się w specyfikacji), **prawa** to dokładnie taki tekst, jaki ma zobaczyć użytkownik w polskim UI / TTS. Do użycia w `i18n/pl.json` lub odpowiedniku.

### 9.1 Stany operacyjne i status awatara

| EN / Termin techniczny | PL (UI/TTS)                            |
|------------------------|----------------------------------------|
| `idle`                 | gotowy                                 |
| `listening`            | słucham…                               |
| `thinking`             | myślę…                                 |
| `speaking`             | mówię                                  |
| `error`                | błąd                                   |
| `degraded`             | tryb ograniczony                       |
| `minimal`              | tryb minimalny                         |
| `healthy`              | wszystko działa                        |
| `sleep`                | śpię                                   |
| `observer active`      | obserwuję                              |
| `conversation lock`    | rozmawiamy                             |
| `crashed`              | poprzednia sesja zakończona awarią     |
| `resumed after hibernate` | wróciłem po hibernacji              |

### 9.2 Komendy głosowe (rozumiane przez Command Matcher)

| EN (intent / akcja kodowa)          | PL (trigger głosowy — co użytkownik mówi) |
|-------------------------------------|--------------------------------------------|
| `go_to_sleep`                       | „Idź spać"                                 |
| `wake_up`                           | „Obudź się"                                |
| `start_observing`                   | „Zacznij obserwować"                       |
| `stop_observing`                    | „Przestań obserwować"                      |
| `silent_mode_on`                    | „Wycisz się"                               |
| `silent_mode_off`                   | „Możesz mówić"                             |
| `make_backup`                       | „Zrób backup"                              |
| `summarize_session`                 | „Podsumuj sesję"                           |
| `open_documents`                    | „Otwórz dokumenty"                         |
| `reload_config`                     | „Przeładuj konfigurację"                   |
| `set_observer_interval`             | „Ustaw interwał na {N} sekund"             |
| `change_persona`                    | „Zmień personę na {nazwa}"                 |
| `set_active_character`              | „Gram teraz {postacią}"                    |
| `forget_about`                      | „Zapomnij o {temat}"                       |
| `refresh_topic` (cache bypass)      | „Odśwież informacje o {temat}"             |

### 9.3 Emocje (16) — etykiety dla logów/debug

W TTS emocje **nie są wymawiane** — modulują tylko speed/pitch. Te etykiety są dla panelu debug i logów.

| EN          | PL              |
|-------------|-----------------|
| `happy`     | radość          |
| `amused`    | rozbawienie     |
| `proud`     | duma            |
| `sympathetic` | empatia       |
| `sad`       | smutek          |
| `disappointed` | rozczarowanie |
| `angry`     | złość           |
| `disgusted` | obrzydzenie     |
| `excited`   | ekscytacja      |
| `scared`    | strach          |
| `surprised` | zaskoczenie     |
| `nervous`   | zdenerwowanie   |
| `thinking`  | zamyślenie      |
| `confused`  | dezorientacja   |
| `nostalgic` | nostalgia       |
| `sarcastic` | sarkazm         |

### 9.4 Komunikaty błędów / degradacji (TTS + overlay)

| Scenariusz / kod                     | Komunikat PL (do TTS / overlay)                                                |
|--------------------------------------|---------------------------------------------------------------------------------|
| `lm_studio_unavailable`              | „Nie mogę teraz myśleć, LM Studio wyłączone."                                  |
| `microphone_missing`                 | „Nie widzę mikrofonu."                                                          |
| `vram_exceeded`                      | „Hmm, brakuje mi pamięci, daj mi sekundę."                                      |
| `internet_unavailable`               | „Nie mam teraz dostępu do internetu, odpowiem z tego co wiem."                  |
| `vlm_scene_unrecognized`             | „Hmm, nie jestem pewien co widzę. Możesz powiedzieć co to za gra?"              |
| `mcp_rate_limited`                   | „Spróbuję szukać za chwilę."                                                    |
| `stt_low_confidence` (0.4–0.7)       | „Nie jestem pewien czy dobrze usłyszałem: *{transkrypcja}*. Czy o to chodziło?" |
| `stt_very_low_confidence` (<0.4)     | „Przepraszam, nie zrozumiałem. Możesz powtórzyć?"                              |
| `minimal_state`                      | „Oczekuję na zasoby…"                                                           |
| `resumed_after_hibernate`            | „O, wróciłeś!"                                                                  |

### 9.5 Komunikaty proaktywne

| Trigger                              | Komunikat PL                                                              | Emocja      |
|--------------------------------------|---------------------------------------------------------------------------|-------------|
| `app_start`                          | „Hej! Co robimy dzisiaj?"                                                  | `happy`     |
| `game_detected`                      | „O, widzę że odpalasz {gra}. Chcesz żebym obserwował?"                     | `excited`   |
| `daily_check_has_results`            | „Hej, mam nowości o meta {gra} — chcesz posłuchać?"                        | `amused`    |
| `game_closed`                        | „Dobra sesja! Chcesz raport?"                                              | `proud`     |
| `season_detected` (PoE2 etc.)        | „Wygląda na nowy sezon. Chcesz zresetować profil buildu?"                  | `excited`   |

### 9.6 Etykiety panelu konfiguracji

| EN / klucz                           | PL (etykieta UI)                          |
|--------------------------------------|-------------------------------------------|
| `language`                           | Język                                     |
| `proactivity_level`                  | Poziom proaktywności                      |
| `quiet_hours`                        | Godziny ciszy                             |
| `content_root`                       | Folder asystenta                          |
| `input_device`                       | Mikrofon                                  |
| `output_device`                      | Głośniki                                  |
| `tts_volume`                         | Głośność asystenta                        |
| `stt_confidence_threshold`           | Próg pewności rozpoznawania               |
| `notification_sound`                 | Ping przed komentarzem                    |
| `default_interval_seconds`           | Interwał obserwatora                      |
| `ambient_enabled`                    | Obserwator poza grą                       |
| `lm_studio_url`                      | Adres LM Studio                           |
| `default_model`                      | Domyślny model                            |
| `max_tool_calls_per_turn`            | Maks. wywołań narzędzi na turę            |
| `streaming`                          | Streaming odpowiedzi                      |
| `backend`                            | Backend bazy                              |
| `archive_days`                       | Dni do archiwizacji                       |
| `semantic_memory_limit`              | Limit pamięci semantycznej                |
| `html_theme`                         | Motyw raportów                            |
| `daily_check_on_startup`             | Codzienny check meta przy starcie         |
| `persona.active`                     | Osobowość                                 |
| `wakeword`                           | Słowo wybudzające                         |
| `audio_mode` (`ptt`/`wakeword`)      | Tryb głosu (Push-to-Talk / Wakeword)      |

### 9.7 Reguły językowe

- **Nazwy własne (gier, filmów, książek, seriali)** zawsze w **oryginalnym brzmieniu**, niezależnie od języka odpowiedzi: `Path of Exile 2`, `Stellaris` (nie „Ścieżka Wygnania 2").
- **Skróty techniczne** (LLM, STT, TTS, VLM, OCR, PTT, MCP, FTS5, VRM, DPS, FPS, GPU, VRAM, API) **nie są tłumaczone** — używaj akronimu.
- **Domyślny język TTS:** polski. Po odpowiedzi po angielsku (na żądanie) — następna odpowiedź **automatycznie** wraca na polski.
- **Kolejność warstw promptu:** `[BASE_SYSTEM_PROMPT] + [PERSONA_PROMPT] + [GAME_PROFILE_CONTEXT] + [OBSERVER_CONTEXT] + [PLAYER_PROFILE] + [LANGUAGE_INSTRUCTION]` — nazwy w UI/dokumentacji zachować bez tłumaczenia (są to identyfikatory).

---

*Wersja `v1.0` — bazuje na PRD 01–06 oraz DB_SCHEMA. Każdy nowy termin dodawany do projektu powinien być najpierw zdefiniowany tutaj.*
