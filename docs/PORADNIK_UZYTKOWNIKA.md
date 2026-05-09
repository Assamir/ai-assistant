# Poradnik użytkownika i konfiguracji — Assystent

Ten dokument zbiera **ścieżki w repozytorium**, **kroki od zera do działającego dev**, **ustawienia w aplikacji** oraz **linki zewnętrzne**. Szczegóły techniczne modeli, VRAM i playbooków: [ENV_SETUP.md](ENV_SETUP.md).

---

## Dokumentacja w repozytorium (spis linków wewnętrznych)

| Temat | Ścieżka |
| --- | --- |
| Środowisko, modele, LM Studio, troubleshooting | [docs/ENV_SETUP.md](ENV_SETUP.md) |
| Historia zmian | [CHANGELOG.md](../CHANGELOG.md) w korzeniu repo |
| README projektu | [README.md](../README.md) |
| Plan implementacji | [docs/plan/implementation_plan_part2.md](plan/implementation_plan_part2.md) |
| Domyślna konfiguracja YAML (wzór) | [backend/config/schema.py](../backend/config/schema.py) — domyślne pola Pydantic |
| Przykład `config.yaml` dev — Piper przy starcie z korzenia repo | [config/config.yaml](../config/config.yaml) |
| Ładowanie YAML + ENV `ASSY_*` | [backend/config/loader.py](../backend/config/loader.py) |
| Skrypt jednorazowy venv + pip | [scripts/setup.ps1](../scripts/setup.ps1) |
| Start dev (Windows, 3 okna) | [scripts/start-dev.bat](../scripts/start-dev.bat) |
| Pobieranie modeli (opcjonalnie) | [scripts/download_models.py](../scripts/download_models.py) |
| Weryfikacja środowiska | [scripts/verify_env.py](../scripts/verify_env.py) |
| Frontend — Electron main | [frontend/electron-main.cjs](../frontend/electron-main.cjs) |
| Frontend — preload (bridge ENV → strona) | [frontend/preload.cjs](../frontend/preload.cjs) |
| Katalog modeli VRM w buildzie dev/prod | [frontend/resources](../frontend/resources) |
| Lista wbudowanych VRM w UI (aktualizuj przy nowym pliku) | [frontend/src/vrmBundledCatalog.ts](../frontend/src/vrmBundledCatalog.ts) |
| Katalog głosów Piper PL (lista rozwijalna w UI) | [frontend/src/piperVoicesCatalog.ts](../frontend/src/piperVoicesCatalog.ts) |
| Synchronizacja głosów Piper do `resources/` | [scripts/sync-piper-voices.ps1](../scripts/sync-piper-voices.ps1) |
| Instalacja binary Piper (Windows ZIP) | [scripts/install-piper-windows.ps1](../scripts/install-piper-windows.ps1) |
| Vite — statyczne `resources` → root `dist` | [frontend/vite.config.ts](../frontend/vite.config.ts) |
| NSIS — instalator tylko klient | [frontend/electron-builder.client.yml](../frontend/electron-builder.client.yml) |
| NSIS — instalator komplet (+ `extraResources` backend) | [frontend/electron-builder.full.yml](../frontend/electron-builder.full.yml) |
| Tekst / BAT pierwszego `pip` (pakiet Komplet) | [frontend/installer-resources-full/](../frontend/installer-resources-full/) |
| Protokół WS (`chat_text`, `ptt_*`) — testy integracyjne | [tests/integration/test_ws_chat.py](../tests/integration/test_ws_chat.py) |
| Plan zdarzeń API / WS (referencja) | [docs/api-plan.md](api-plan.md) |

---

## Narzędzia z Internetu — oficjalne strony pobrania / dokumentacji

| Narzędzie | Link |
| --- | --- |
| Python | [https://www.python.org/downloads/](https://www.python.org/downloads/) |
| Node.js (LTS) | [https://nodejs.org/](https://nodejs.org/) |
| Git | [https://git-scm.com/](https://git-scm.com/) |
| LM Studio | [https://lmstudio.ai/](https://lmstudio.ai/) |
| Sterowniki NVIDIA | [https://www.nvidia.com/Download/index.aspx](https://www.nvidia.com/Download/index.aspx) |
| Visual Studio Build Tools 2022 (C++) | [https://visualstudio.microsoft.com/downloads/](https://visualstudio.microsoft.com/downloads/) |
| Piper (TTS, Windows) — release | [https://github.com/rhasspy/piper/releases](https://github.com/rhasspy/piper/releases) |
| PyTorch (instalacja z CUDA) | [https://pytorch.org/get-started/locally/](https://pytorch.org/get-started/locally/) |
| VRoid Hub (modele VRM, przykłady) | [https://hub.vroid.com/](https://hub.vroid.com/) |

---

## Cisza nocna (`quiet_hours_*`)

Asystent może **nie odtwarzać TTS** (głos z czatu PTT/tekstu, komentarze obserwatora, krótki WAV z REST `voice/process` / `voice/synthesize`) w zdefiniowanym oknie czasu — zamiast tego pojawia się tekst na overlayu (`text_overlay`), tak jak w trybie cichym obserwatora.

- **`quiet_hours_enabled`** (`false` domyślnie): włącza logikę okna czasu.
- **`quiet_hours_start`** / **`quiet_hours_end`**: format `HH:MM`, czas **lokalny** komputera; obsługiwane okno przez północ (np. `23:00`–`07:00`).
- ENV: `ASSY_QUIET_HOURS_ENABLED`, `ASSY_QUIET_HOURS_START`, `ASSY_QUIET_HOURS_END`.
- Stan „aktywna cisza teraz”: pole `quiet_hours` w odpowiedzi `GET /api/v1/status`.

Obserwator nadal generuje komentarze tekstowo; wyłączony jest **dźwięk** (w tym ping przed komentarzem w godzinach ciszy).

---

## MCP i dostęp do internetu

Projekt jest **offline-first**. Ruch HTTP poza LM Studio na localhost działa **tylko wtedy**, gdy:

1. W konfiguracji **`mcp.enabled: true`** (ENV: `ASSY_MCP__ENABLED`).
2. Opcjonalna lista **`mcp.tools_enabled`** nie wyklucza danego narzędzia (pusta lista = wszystkie zarejestrowane przy włączonym MCP).
3. Narzędzia **`web_search`** i **`web_scraper`** nie są wywoływane z pętli obserwatora ekranu — sieć pojawia się przy **function calling** w turze czatu oraz w **jawnych ścieżkach** (np. dzienne meta, hint ligi, import buildu z URL).

**Polityka krótka:**

- Tryb offline (`online: false` w stanie orkiestratora) blokuje `web_search` / `web_scraper`.
- Limit **`mcp.web_search_calls_per_minute`** obejmuje **łącznie** oba narzędzia (ochrona przed zalewem żądań).
- **`mcp.scraper_allowed_hosts`**: opcjonalna lista hostów (np. `maxroll.gg`) — gdy niepusta, `web_scraper` akceptuje tylko te domeny (bez prefiksu `www.` w konfiguracji — dopasowanie jest normalizowane).
- Logi backendu: wywołania sieciowe MCP zapisują **prefiks skrótu argumentów** (SHA-256), bez treści zapytania w plain text (`mcp_network_call`).

Szczegóły backlogu produktowego: [docs/plan/FUTURE_IMPROVEMENTS.md](plan/FUTURE_IMPROVEMENTS.md).

---

## Szybka ścieżka: co zrobić po kolei

### Faza A — jednorazowo na komputerze

1. Zainstaluj **Python 3.11+**, **Node.js 22 LTS**, **Git**, **sterowniki NVIDIA** (jeśli masz GPU), ewentualnie **Build Tools VS 2022** z obciążeniem „Desktop development with C++” (wymagane przez część pakietów — opis w [ENV_SETUP.md](ENV_SETUP.md), rozdz. 2.4).
2. Sklonuj repozytorium i przejdź do katalogu głównego projektu (np. `c:\code\_repos\antigravity\assystent`).
3. Przygotuj **content root** z danymi i konfiguracją (domyślnie w dokumentacji: `c:\ai\asystent\`) — skrypt katalogów i drzewo: [ENV_SETUP.md](ENV_SETUP.md), rozdz. 3.2–3.3.
4. Skopiuj lub utwórz `config\config.yaml` w content root (wzór: [config.default.yaml](../backend/config/config.default.yaml)).
5. Utwórz venv i zainstaluj backend:
   ```powershell
   cd c:\code\_repos\antigravity\assystent
   powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
   ```
6. Zgodnie z [ENV_SETUP.md](ENV_SETUP.md), rozdz. 4.3: `playwright install chromium` (po pierwszym `pip install`).
7. Pobierz modele (Whisper, embeddingi, Moondream itd.) — [ENV_SETUP.md](ENV_SETUP.md), rozdz. 5 oraz [scripts/download_models.py](../scripts/download_models.py).
8. **LM Studio**: pobierz, załaduj model z obsługą **function calling**, włącz serwer lokalny (domyślnie `127.0.0.1:1234`, CORS włączony) — [ENV_SETUP.md](ENV_SETUP.md), rozdz. 6.
9. Weryfikacja:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   python scripts\verify_env.py
   ```

### Faza B — każda sesja developerska

#### Uruchomienie „jedną komendą” (Windows — całość: backend + Vite + Electron)

Warunek wstępny: **LM Studio** jest uruchomione z załadowanym modelem i włączonym serwerem HTTP ([ENV_SETUP.md](ENV_SETUP.md), rozdz. 6 oraz 8.1).

**Z korzenia repozytorium**, jedna komenda dla użytkownika:

```bat
scripts\start-dev.bat
```

lub **PowerShell** (podmień ścieżkę na swój klon):

```powershell
cd C:\ścieżka\do\assystent
.\scripts\start-dev.bat
```

Co robi [scripts/start-dev.bat](../scripts/start-dev.bat):

- wymaga wcześniejszego [setup.ps1](../scripts/setup.ps1) (obecność `.venv`);
- ewentualnie **doinstaluje** `python-multipart`; przy pierwszym razie **`npm ci`** w `frontend/`;
- otwiera **trzy osobne okna CMD**: backend `:8000`, Vite `:5173`, Electron z `ASSYSTENT_DEV=1`;
- zamknięcie okna kończy tylko dany proces (niejeden demon w tle).

Pusty ekran Electron: poczekaj na Vite lub uruchom ponownie samo Electron — jak w komunikacie końcowym skryptu bat.

To nadal **jedna akcja startu środowiska dev** od Ciebie; **LM Studio** musi być włączone osobno (przed lub tuż po skrypcie).

**Ręcznie** zamiast bat: [README.md](../README.md) oraz [ENV_SETUP.md](ENV_SETUP.md), rozdz. 8.2 i 8.4.

**Kolejność logiczna:** LM Studio → backend → frontend ([ENV_SETUP.md](ENV_SETUP.md), rozdz. 8.1).

---

### Rozmowa z agentem — jak uruchomić dialog

Backend realizuje narzędzia / MCP zgodnie z konfiguracją. Najprostsze ścieżki:

#### A) Electron — panel WebSocket (obecny interfejs)

1. Karta **Połączenie:** ustaw i zapisz **URL backendu** (np. `http://127.0.0.1:8000`) — **`assystent.apiBaseUrl`**.
2. Poczekaj na **podłączenie WebSocket** (status jak w aplikacji; zdarzenia w logu poniżej przycisków).
3. **Frontend ready** — rejestruje kontekst sesji WS ([ws_router](../backend/api/ws_router.py)).
4. **Wiadomość do agenta** — pole tekstowe + przycisk **Wyślij** (Enter wysyła, Shift+Enter nowa linia); zdarzenie **`chat_text`**. Jeśli masz **TTS**, w logu pojawi się też **`audio_stream`** (lip-sync avataru — [App.tsx](../frontend/src/App.tsx)); bez TTS zobaczysz **`text_overlay`** oraz podpis pod avatarem „Odpowiedź (tekst, bez nagłośnika)”.
5. **Trzymaj — mów** — **push-to-talk**: przytrzymaj przycisk, puść po wypowiedzi; klient nagrywa **mono 16 kHz WAV** i wysyła **`audio`** w **`ptt_end`**. Backend musi mieć działający **STT**. Przy pierwszym użyciu Electron/Chromium pyta o **mikrofon** — dla okna Electron uprawnienie **`media`** jest domyślnie przyjmowane w [electron-main.cjs](../frontend/electron-main.cjs).
6. **Zatrzymaj audio** — przerywa odtwarzanie strumienia WAV z WS.

Szczegóły eventów oraz **`ptt_start` / `ptt_end`**: [tests/integration/test_ws_chat.py](../tests/integration/test_ws_chat.py), [docs/api-plan.md](api-plan.md).

#### B) REST — sama treść zapytania (`/voice/chat`)

Pełny turn agenta bez Electron:

```powershell
curl -s -X POST "http://127.0.0.1:8000/api/v1/voice/chat" `
  -H "Content-Type: application/json" `
  -d "{\"text\":\"Cześć, opowiedz krótko co potrafisz.\"}"
```

Odpowiedź zawiera m.in. **`content`**, **`emotion`**, **`tool_calls`**. Wariant strumieniowy: ustaw **`\"stream\": true`** w JSON lub nagłówek `Accept: text/event-stream` — zobacz `voice_chat` w [routes.py](../backend/api/routes.py).

#### C) REST — nagranie głosu → STT → agent (`/voice/process`)

**`POST /api/v1/voice/process`** z polem formularza **`audio`** (plik WAV itd.). Backend transkrybuje (`stt_engine`) i odpali tę samą ścieżkę co czat tekstowy. Wymaga działającego STT w Twojej instalacji:

```powershell
curl -s -X POST "http://127.0.0.1:8000/api/v1/voice/process" `
  -F "audio=@C:\temp\nagranie.wav"
```

Alternatywy: **`POST /api/v1/voice/transcribe`**, **`POST /api/v1/voice/synthesize`** — próbki poleceń [ENV_SETUP.md](ENV_SETUP.md), rozdz. 8.3.

#### D) WebSocket push-to-talk w kliencie React

Electron / przeglądarka: przycisk **„Trzymaj — mów”** nagrywa krótki **WAV PCM mono 16 kHz** po **`ptt_start`** i przy puszczeniu wysyła **`ptt_end`** z **`payload.audio`** (Base64, konwencja jak w [test_ws_chat.py](../tests/integration/test_ws_chat.py)). Ścieżka STT jest w backendzie — **`stt_*`** musi być poprawnie skonfigurowane.

#### Backendowy „PTT” (klawiatura) — `audio.backend_ptt_listener_enabled`

W `config.yaml` można włączyć nasłuch **pynput** w procesie Pythona (**`caps_lock`** domyślnie lub `ptt_key_name` jak w [voice_input.py](../backend/ai/voice_input.py)). Służy m.in. do sygnałów **`LISTENING`** / **`audio_duck`** i pomija cykl obserwatora przy trzymanym klawiszu — **to nie jest samodzielne nagrywanie z mikrofonu** do backendu bez klienta wysyłającego PCM (REST lub WS jak wyżej).

#### Skróty Electron ([electron-main.cjs](../frontend/electron-main.cjs))

| Skrót | Działanie |
| --- | --- |
| **Ctrl+Shift+S** | Pokazuje / fokusuje okno |
| **Ctrl+Shift+A** | Otwiera DevTools (gdy zamknięte) |

---

## Porty i adresy domyślne

| Usługa | Adres | Uwagi |
| --- | --- | --- |
| Backend FastAPI | `http://127.0.0.1:8000` | REST + WebSocket |
| WebSocket (domyślnie) | `ws://127.0.0.1:8000/ws` | Ustawialny w preload / ENV |
| Vite (dev) | `http://127.0.0.1:5173` | Tylko gdy `ASSYSTENT_DEV=1` w Electron |
| LM Studio (OpenAI-compatible) | `http://127.0.0.1:1234` | Typowo `/v1` w `config.yaml` |

**Szybki test backendu:**

```powershell
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/status
```

---

## Aplikacja Electron — panel konfiguracji (UI)

Ustawienia są w prawym panelu kart.

### Karta „Połączenie”

- **URL backendu (REST)** — zapis w przeglądarce / Electron: klucz `localStorage` **`assystent.apiBaseUrl`** (np. `http://127.0.0.1:8000`).
- **WebSocket** — wyświetlany adres pochodzi z `window.assystent.wsUrl` (preload) lub zmiennej Vite `VITE_WS_URL` w buildzie; domyślnie `ws://127.0.0.1:8000/ws` ([preload.cjs](../frontend/preload.cjs)).
- Przy stronie otwartej z **`file://`** aplikacja normalizuje bazę API (nie używa schematu `file` jako hosta) — szczegóły w [CHANGELOG.md](../CHANGELOG.md).

### Karta „Avatar”

- **Lista modeli** — pliki `.vrm` z katalogu [frontend/resources](../frontend/resources) (w produkcji kopiowane obok `index.html` dzięki `publicDir: resources` w [vite.config.ts](../frontend/vite.config.ts)).
- **Domyślny model** przy pierwszym uruchomieniu (gdy nie ma zapisu użytkownika, bridge ani `VITE_VRM_URL`): **`./kaguya_watanuki.vrm`**.
- **„Inny adres URL…”** — pozwala wpisać zewnętrzny adres (HTTPS z CORS lub host lokalny), jak wcześniej jedno pole URL.
- Zapis wyboru: **`localStorage`** → klucz **`assystent.vrmUrl`**.
- **Nowy plik `.vrm` w `frontend/resources`:** dodaj nazwę pliku do tablicy w [vrmBundledCatalog.ts](../frontend/src/vrmBundledCatalog.ts) (lista musi być zsynchronizowana z folderem — patrz [CHANGELOG.md](../CHANGELOG.md)).

**Nadpisanie z ENV (Electron):** `ASSYSTENT_VRM_URL` lub `VITE_VRM_URL` — patrz [ENV_SETUP.md](ENV_SETUP.md), rozdz. 11.3.

### Karta „Więcej”

- **Pobierz status** — `GET {apiBase}/api/v1/status` (przeładowuje też wskaźnik TTS na stronie głównej).
- **TTS — głos Piper** — pole **absolutnej** ścieżki do katalogu [frontend/resources](../frontend/resources) (w nim `piper-voices/…`), lista rozwijalna głosu (zob. [piperVoicesCatalog.ts](../frontend/src/piperVoicesCatalog.ts)), opcjonalnie ścieżka do `piper.exe`, przycisk **Zastosuj głos TTS** (`PUT /api/v1/config` jak poniżej). Duże pliki `.onnx` są ignorowane w gicie — synchronizacja: [scripts/sync-piper-voices.ps1](../scripts/sync-piper-voices.ps1).
- **TTS — prędkość głosu** — `PUT /api/v1/config` (wymaga zapisanej konfiguracji w `content_root`). Przy włączonym tokenie ochrony ustaw ten sam sekret co backend — poniżej.

---

## Backend — konfiguracja plików i zmiennych środowiskowych

### Główny plik YAML

- Lokalizacja: `{content_root}/config/config.yaml` (content root ustawiasz w konfiguracji ogólnej aplikacji, domyślna ścieżka opisana w [ENV_SETUP.md](ENV_SETUP.md), rozdz. 3).

### Prefiks `ASSY_*`

- Nadpisują pola YAML wg wzorca `ASSY_<SEKCJA>__<POLE>` (podwójne `__` dla zagnieżdżeń).
- Pełniejszy opis: [ENV_SETUP.md](ENV_SETUP.md), rozdz. 11.2; implementacja: [loader.py](../backend/config/loader.py).

### Przykład: podpowiedź ligi po wykryciu gry (T8)

- Zmienna: `ASSY_OBSERVER__AUTO_LEAGUE_HINT_ON_GAME_DETECTED` = `1` lub `true`  
- Alternatywa w YAML: `observer.auto_league_hint_on_game_detected: true`  
- Opis: [ENV_SETUP.md](ENV_SETUP.md), rozdz. 11.2.

### CORS (gdy klient z innego originu niż backend)

- `ASSYSTENT_CORS_ORIGINS` — [ENV_SETUP.md](ENV_SETUP.md), rozdz. 11.1.

### Ochrona `PUT /api/v1/config`

- Backend: `ASSYSTENT_CONFIG_PUT_TOKEN` — nagłówek `X-Config-Put-Token` lub `Authorization: Bearer …` ([ENV_SETUP.md](ENV_SETUP.md), rozdz. 11.5).
- Frontend: `VITE_CONFIG_PUT_TOKEN`, `ASSYSTENT_CONFIG_PUT_TOKEN` w preload, lub `localStorage['assystent.configPutToken']` ([ENV_SETUP.md](ENV_SETUP.md), rozdz. 11.5 i karta „Więcej” w aplikacji).

---

## Frontend / Electron — zmienne środowiskowe

| Zmienna | Zastosowanie |
| --- | --- |
| `ASSYSTENT_DEV=1` | Tryb deweloperski: ładowanie `http://localhost:5173`, DevTools ([electron-main.cjs](../frontend/electron-main.cjs)). |
| `VITE_DEV_SERVER_URL` | Opcjonalny URL serwera Vite (domyślnie `http://localhost:5173`). |
| `ASSYSTENT_WS_URL` / `VITE_WS_URL` | Pełny URL WebSocket ([preload.cjs](../frontend/preload.cjs)). |
| `ASSYSTENT_API_URL` / `VITE_API_BASE_URL` | Baza REST ([preload.cjs](../frontend/preload.cjs)). |
| `ASSYSTENT_VRM_URL` / `VITE_VRM_URL` | Domyślny URL modelu VRM (nad `localStorage`, jeśli ustawione w bridge). |
| `ASSYSTENT_CONFIG_PUT_TOKEN` / `VITE_CONFIG_PUT_TOKEN` | Token do `PUT /api/v1/config` z UI. |
| `ASSYSTENT_NO_AUTO_BACKEND=1` | Instalator Komplet: nie uruchamiaj `uvicorn` z bundlowanego backendu przy starcie ([electron-main.cjs](../frontend/electron-main.cjs)). |
| `ASSYSTENT_PYTHON_EXE` | Instalator Komplet: pełna ścieżka do `python.exe`, gdy `python` nie jest w PATH. |

Szczegóły zbiorczo: [ENV_SETUP.md](ENV_SETUP.md), rozdz. 11.3.

---

## Release Windows (installer)

1. Frontend: z katalogu [frontend](../frontend):
   - **`npm run electron:dist`** lub **`npm run electron:dist:client`** — instalator tylko klient → `electron-release-out/client/Assystent-Client-Setup-0.1.0.exe`
   - **`npm run electron:dist:full`** — klient + kod backendu i `requirements.txt` w `resources` → `electron-release-out/full/Assystent Komplet-Setup-0.1.0.exe`
   - **`npm run electron:dist:all`** — oba powyższe
2. Ikona: [frontend/resources/icon.png](../frontend/resources/icon.png). Konfiguracja: [electron-builder.client.yml](../frontend/electron-builder.client.yml), [electron-builder.full.yml](../frontend/electron-builder.full.yml).
3. **Komplet:** po instalacji przeczytaj `resources\bundled\docs\README-KOMPLET.txt` i przy pierwszym użyciu uruchom **`Pierwsze-zaleznosci-backend.bat`** (albo ręcznie `pip install -r ...` w `resources\bundled\python-app`).

Polityka: nie wklejaj sekretów do repo; dla użytkownika końcowego dostarczaj binaria + `content_root`, `config`, dane ([README.md](../README.md)).

---

## Problemy? (troubleshooting)

Skrót najczęstszych przypadków: [ENV_SETUP.md](ENV_SETUP.md), rozdz. 9 (CUDA OOM, Piper, mikrofon, port 1234, DXcam / AV).

---

## Checklista przed pierwszym startem backendu

Wersja rozszerzona: [ENV_SETUP.md](ENV_SETUP.md), sekcja „Checklista gotowości (pre-start)” pod koniec dokumentu. Minimum:

- `python scripts/verify_env.py` bez krytycznych braków.
- LM Studio działa na oczekiwanym porcie i model ma **function calling**.
- `config.yaml` w content root spójny z ścieżkami modeli (Whisper, Piper, itd.).
- Frontend: `npm ci` wykonane w [frontend](../frontend) (albo pierwsze uruchomienie [start-dev.bat](../scripts/start-dev.bat)).

---

*Ostatnia aktualizacja poradnika: 2026-05-06 — jedna komenda startu (`start-dev.bat`) i ścieżki rozmowy z agentem (UI, REST, głos, WS PTT).*
