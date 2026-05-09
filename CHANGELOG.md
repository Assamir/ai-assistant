# Changelog — Assystent

All notable changes to this project are documented here. The format is inspired by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **Transparent frameless overlay window (F-AV-02):** Electron główne okno jest teraz `frame: false`, `transparent: true`, `alwaysOnTop: true`. Awatar zajmuje cały obszar okna z przezroczystym tłem. Pasek przeciągania (28 px) u góry; dolny pasek kontrolny (PTT, Śpij, Cichy, Klik-przez, ⚙). Overlay wyświetla napisy asystenta/obserwatora, toast PTT, baner profilu i kolorową kropkę stanu (szary/niebieski/amber/zielony = idle/listening/thinking/speaking).
- **`visual_state` WS event handling:** Backend wysyła `visual_state` (`idle`|`listening`|`thinking`|`speaking`) przy każdej zmianie fazy. Frontend śledzi `visualState` i aktualizuje kolorową kropkę stanu w overlayowym widoku Electron.
- **Emocjonalne animacje ciała (proceduralne):** `AvatarCanvas` ma teraz tabelę `EMOTION_BODY` z 17 zestawami parametrów (amplituda/częstotliwość kołysania X/Z, przechylenie głowy Z, skłon X). Parametry są spring-lerped między emocjami (`1 - exp(-delta * 1.5)`). Kości głowy (neck/head) animowane oddzielnie z 35%/25% amplitudy ciała + statyczne przesunięcia z emocji.
- **Spring bones — drugi pass:** `vrm.springBoneManager?.update(delta)` wywoływane PO ręcznej manipulacji kościami ciała i głowy, dzięki czemu włosy/ubrania reagują na nasze kołysanie.
- **Selektor urządzenia wejściowego (F-VO-06):** Dropdown mikrofonu w sekcji PTT; wybór zapisywany w `localStorage["assystent.micDeviceId"]`; przekazywany do `getUserMedia` jako `{ exact: deviceId }`.
- **Selektor urządzenia wyjściowego (F-VO-07):** Dropdown głośników (gdy przeglądarka listuje `audiooutput`); zapisywany w `localStorage["assystent.outputDeviceId"]`; przekazywany do `AudioContext.setSinkId()` w `useAudioStreamPlayer`. Etykieta suwaka głośności pokazuje aktywne urządzenie.
- **Idle blink (F-AV-05):** `AvatarCanvas` generuje losowe mrugnięcia co 2.5–7.5 s (zamknięcie 70 ms, otwarcie 90 ms) przez blendshape `blink` VRM.
- **Audio duck przy PTT:** `useAudioStreamPlayer` eksportuje `duck(targetVolume, rampMs)` — płynne ściszanie TTS przez `GainNode.linearRampToValueAtTime` skalowane przez `outputVolume` użytkownika. `App.tsx` obsługuje zdarzenie WS `audio_duck` emitowane przez backend przy `ptt_start` (0.0) i `ptt_end` (1.0).
- **CMD-21 — „zapomnij o X":** Komenda głosowa usuwająca chunki bazy wiedzy (`SemanticRecall.remove_knowledge_chunks_where`) według `source_path` = `{topic}.md` lub `{slug}.md`. Działa przez `orchestrator._semantic_recall`; zwraca liczbę usuniętych chunkó. REST: `DELETE /api/v1/knowledge?source_path=...` (503 gdy `memory.enabled: false`).
- **Osobne okno konfiguracyjne (Electron):** `createConfigWindow()` otwiera standardowe okno `BrowserWindow` ładujące `index.html#config`. Dostępne z menu tray, przycisku ⚙ w dolnym pasku overlay i przycisku „Kreator startowy" w widoku przeglądarki.
- **ConfigPanel — zakładki Obserwator i Persona:**
  - *Obserwator* — wskaźniki stanu (aktywny/śpiący/cichy), przyciski toggle (obserwator/sen/tryb cichy), pole interwału z przyciskiem „Ustaw".
  - *Persona* — lista plików `.md` z `GET /api/v1/personas` (id + display_name + aktywna), przycisk „Aktywuj" wysyłający `zmień personę na {id}`.
- **Config PUT token w UI:** Pole hasła w zakładce Połączenie ConfigPanelu; zapisuje/usuwa `localStorage["assystent.configPutToken"]`.
- **`GET /api/v1/personas`** — endpoint REST listujący pliki person z `personas/` (id, display_name) oraz aktywną personę z `orchestrator.state`.
- **Testy CMD-21:** 6 przypadków (basic match, multiword topic, diacritics, empty-topic non-match, cmd_id, priority ordering).
- **Testy `DELETE /api/v1/knowledge`:** 4 przypadki (503 brak memory, 200 z liczbą, source_path forwarded, zero-removed OK).

- **Voice → REST commands (T8):** Trzy nowe komendy głosowe mapowane bezpośrednio na logikę REST:
  - `CMD-19` — „sprawdź hint ligi" / „sprawdź ligę" → wywołuje `analyze_league_hint` dla aktywnej gry; informuje głosowo o zgodności lub rozbieżności z profilem.
  - `CMD-20` — „sprawdź meta" / „co nowego w grze" → wywołuje `run_daily_meta_check_for_game`; informuje o nowościach lub braku zmian.
  - `CMD-08` (poprawka) — „podsumuj sesję" → prawdziwe zapytanie do SQLite (`messages` po `session_id`); wcześniej był stub.
  - Komendy działają przez `SimpleOrchestratorContext._services` — `league_hint_fn`/`daily_check_fn` wstrzykiwane z `app_context.py` po stworzeniu `ctx` (unikanie circular dep). Cooldown: CMD-19 = 30 s, CMD-20 = 120 s.
- **LICENSES.md** — lista wszystkich bibliotek open-source (backend Python + frontend JS/Electron), modeli AI i licencji; placeholder dla awatara VRM do uzupełnienia po wyborze modelu.
- **Testy sandbox audit** (`tests/unit/test_sandbox_audit.py`) — 13 przypadków: path traversal (`../../etc/passwd`, ścieżki bezwzględne poza root, `..` w środku), walidacja URL (blokada `file://`, `javascript:`, `ftp://`, pusta), tryb offline (`OfflineModeError`).

- **Docs:** [docs/PORADNIK_UZYTKOWNIKA.md](docs/PORADNIK_UZYTKOWNIKA.md) — zbiorczy poradnik użytkownika i konfiguracji (kroki, porty, panel UI, ENV, **`start-dev.bat` jako jedna komenda**, rozmowa z agentem przez UI/`voice/chat`/`voice.process`, WS PTT — linki). README linkuje ten plik na początku.
- **Frontend / Avatar:** lista rozwijana modeli VRM z wbudowanego katalogu (pliki w `frontend/resources`, Vite `publicDir: resources`); domyślny model `./kaguya_watanuki.vrm` gdy brak `localStorage` / bridge Electron / `VITE_VRM_URL`. Opcja „Inny adres URL…” z polem jak dotychczas dla zewnętrznych plików — przy nowym modelu w folderze dopisz nazwę pliku w `src/vrmBundledCatalog.ts`.
- **T8 / Auto league hint:** `observer.auto_league_hint_on_game_detected` (YAML) lub `ASSY_OBSERVER__AUTO_LEAGUE_HINT_ON_GAME_DETECTED` — po `game_detected` z znanym `game_id` uruchamia `check-league-hint`; przy `mismatch_hint` broadcast WS `player_profile.league_hint` (jak REST `broadcast: true`). Dokumentacja ENV: `docs/ENV_SETUP.md` §11.2.
- **Frontend:** baner + badge „Liga” (karta Połączenie) dla WS `player_profile.league_hint` oraz `player_profile.league_changed`.
- Desktop packaging: `electron-builder` Windows (NSIS) — dwa instalatory konfiguracyjnie w `electron-builder.client.yml` / `electron-builder.full.yml`; ikona `frontend/resources/icon.png`.
- **Dev (Windows):** `scripts/start-dev.bat` — backend uvicorn (--reload), Vite, Electron (`ASSYSTENT_DEV=1`), opcjonalnie pierwszy `npm ci` w `frontend/`.
- Avatar UX: crossfade (~0.42s, ease-out) between VRM expression weights when the WebSocket `emotion` changes; richer scene lighting (`hemisphereLight` + dual pulsing fill/key `pointLight`s).
- **T8 / Player profile:** `POST /api/v1/player-profile/games/{game}/archive` — writes the current YAML slice for that game to SQLite `player_profile_archives` (`season`, `reason` ∈ `season_reset` | `manual` | `backup`); does **not** clear live `player_profile.yaml` (see PRD / api-plan). `GET /api/v1/player-profile/archives` lists rows (optional `game`, `limit`).
- **T8 / League hint:** `POST /api/v1/player-profile/games/{game}/check-league-hint` `{ "broadcast"?: bool }` — `web_search` (gdy MCP), heurystyka: czy tekst z wyników zawiera **zapisaną** `league` profilu; `mismatch_hint` / `archive_suggested` (bez auto-zapisu). Opcjonalny WS **`player_profile.league_hint`** gdy `broadcast: true` i rozbieżność.
- **T8 / Player profile commands:** `PATCH /api/v1/player-profile/games/{game}` — optional `league` / `game_version` (pusty PATCH → 400); przy zmianie **niepustej** ligi odpowiedź zawiera `archive_recommended` i broadcast WS **`player_profile.league_changed`** (bez auto-archiwum). `POST /api/v1/player-profile/games/{game}/active-character` `{ "character" }` — 422 gdy postaci nie ma na liście.
- **T8 / Daily meta:** `POST /api/v1/daily-checks/run` `{ "game", "force" }` — inserts `daily_checks`, updates `last_meta_check` in profile YAML, optional DuckDuckGo `web_search` when MCP enabled; `GET /api/v1/daily-checks` lists history. **Persists** a Markdown note under `{content_root}/{memory.knowledge_dir}/daily_checks/` and sets DB `knowledge_file_path`; **re-ingests** that file into Chroma when `memory.enabled` and ingester is present. Background: `mcp.daily_check_on_startup` / `ASSY_MCP__DAILY_CHECK_ON_STARTUP`, `daily_check_interval_hours`. WS `daily_check.complete`.

### Fixed

- Electron / strona `file://`: domyślny URL API nie używa już schematu `file` (było `file://127.0.0.1:8000` → `fetch` się wywalał); zawsze `http://127.0.0.1:8000` lub normalizacja `localStorage` / wpisu użytkownika (`normalizeApiBaseUrl`). WebSocket przy `file://` wymusza port backendu `:8000`.

### Changed

- **Frontend / Windows installers:** Dwa instalatory NSIS (`electron-builder.client.yml` / `electron-builder.full.yml`): tylko klient lub **Komplet** (klient + `backend/` i `requirements.txt` w `resources`, dokumentacja i BAT w `installer-resources-full`). Artefakty: `electron-release-out/client/`, `electron-release-out/full/`. Skrypty: `npm run electron:dist` ≡ `electron:dist:client`; dodano `electron:dist:full` i `electron:dist:all`. `electron-main.cjs` przy wykryciu bundlowanego backendu uruchamia `uvicorn` (zmienne: `ASSYSTENT_NO_AUTO_BACKEND`, `ASSYSTENT_PYTHON_EXE`). Ustawienia `electron-builder` w YAML (usunięto z `frontend/package.json` pole `build`). `cross-env CSC_IDENTITY_AUTO_DISCOVERY=false`, `signAndEditExecutable: false`. README, ENV_SETUP, poradnik, `.gitignore`.

- Avatar: jawna mapa wszystkich emocji z `emotions.json` na rodziny palet w `AuraLights` (fallback rodziny: neutral); exponential kołysanie tułowia w idle i lerp barw świateł bez zmiany logiki crossfade ekspresji.
- Refactored emotion weight math into `frontend/src/emotionBlend.ts` (shared helpers for normalization and blending).
