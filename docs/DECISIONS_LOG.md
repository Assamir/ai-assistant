# Decyzje Projektowe — Odpowiedzi na Pytania z Planu Pre-Implementation

> **Status:** v1.2 — Komplet decyzji z sesji 2026-04-27; § „Stan implementacji” 2026-05-09
> **Cel dokumentu:** Single source of truth dla decyzji podjętych w trakcie generowania planu PRE_IMPLEMENTATION_PLAN.md.
> **Użycie:** Załącz ten dokument **do każdego promptu** generującego dokumentację (DOK-01 … DOK-16). Zapobiega niespójnościom i ponownemu zadawaniu pytań.

---

## DOK-02: ENV_SETUP.md

| # | Pytanie | Decyzja |
|---|---------|---------|
| 1 | Domyślny LLM | **Gemma 4 E4B**. Jeśli wydajność niewystarczająca — downgrade do mniejszych modeli (do określenia w trakcie testów Fazy 1, np. Gemma 2 2B, Llama 3.2 3B, Qwen 2.5 3B). LM Studio musi wspierać function calling. |
| 2 | Głos Piper | **`pl_PL-gosia-medium`** — jedyny dostępny żeński głos PL w repozytorium. Jakość medium (brak high dla żeńskiego PL). Pliki lokalne: `C:\code\_repos\antigravity\piper-voices\pl\pl_PL\gosia\medium\`. Licencja CC0. Fallback męski: `pl_PL-bass-high` (wyższa jakość, ale głos męski). |
| 3 | Wakeword | **"Hej {imię_asystenta}"**. Imię konfigurowalne, wybór z **listy dostępnych imion** (wymagane custom training openWakeWord lub gotowe modele). Lista finalnych imion do specyfikacji w DOK-02. Fallback: jeśli custom training problematyczny → predefiniowany model np. "Hey Jarvis". |
| 4 | Domyślny VRM | **VRoid Hub (CC-BY, gotowy model)**. Wybrany model anime-stylizowany z licencją CC-BY z [VRoid Hub](https://hub.vroid.com/). Wymagana atrybucja w aplikacji (sekcja "Credits" w Config Panel + plik `LICENSES.md` w content root). Konkretny model do wyboru w trakcie DOK-02 (kryteria: rozmiar pliku <30MB, pełen zestaw blendshapes, full humanoid bones, język interfejsu autora EN/JP). Backup plan: gdyby model został usunięty z VRoid Hub przed releasem, drugi backup model w `models/avatar/fallback.vrm`. |

---

## DOK-03: CONFIG_SPEC.md

| # | Pytanie | Decyzja |
|---|---------|---------|
| 1 | Precedens źródeł konfiguracji | **env > config**. Zmienne środowiskowe nadpisują wartości z `config.yaml`. Hierarchia: `defaults → config.yaml → env vars`. |
| 2 | Komunikacja błędów config | **Mów głosowo** + log. Asystent po starcie informuje: "Wykryłem błąd w konfiguracji: [klucz]. Używam wartości domyślnej." (emocja `confused` lub `disappointed`). |
| 3 | Quiet hours | **Globalne**, jak w PRD. Jedna para godzin start/end dla całego tygodnia. Nie per-day-of-week (overengineering dla MVP). |

---

## DOK-05: PROMPT_SPEC.md

| # | Pytanie | Decyzja |
|---|---------|---------|
| 1 | Limit długości odpowiedzi w trybie głosowym | **Soft hint** w system prompcie ("staraj się zmieścić w ~80 słowach gdy to rozmowa"), bez twardego truncate. LLM ma swobodę gdy temat wymaga więcej. |
| 2 | "Nie wiem" gdy MCP nie pomógł | **TAK**. Asystent może otwarcie powiedzieć "nie wiem" lub "nie znalazłem". Może **dopytać użytkownika** o dodatkowe info / inne sformułowanie pytania ("Czy chodziło Ci o X? A może Y?"). **HARD RULE: zero halucynacji**. Lepiej powiedzieć "nie wiem" niż zmyślić. To musi być jedna z kluczowych instrukcji w base prompcie + pomocnicza w persona prompts. |
| 3 | Persona wpływa na decyzje o tool use | **NIE**. Persona kontroluje TYLKO ton odpowiedzi. Logika "kiedy użyć web_search" jest globalna, w base prompt. |

---

## DOK-07: COMMANDS_SPEC.md

| # | Pytanie | Decyzja |
|---|---------|---------|
| 1 | Fuzzy matching domyślnie | **TAK włączony**. Tolerancja błędów STT > precyzja. Konfigurowalny przez `command_match_fuzzy: true/false`. Levenshtein distance ≤ 2. |
| 2 | Confirmation dla "Zrób backup" | **NIE**. Backup to non-destructive — tworzy ZIP, nie usuwa nic. Wykonanie natychmiastowe, bez potwierdzenia. |
| 3 | Custom komendy mogą wywoływać MCP tools | **TAK**. User może w `commands.yaml` zdefiniować np. trigger "sprawdź pogodę w X" → akcja `mcp_tool_call` → `web_search("pogoda X")`. Wymaga rozszerzenia schemy custom komend o pole `action_type: builtin | mcp_tool_call | sequence`. |

---

## DOK-09: OBSERVER_SPEC.md

| # | Pytanie | Decyzja |
|---|---------|---------|
| 1 | Dostęp do screenshotów PoE2/Stellaris | **Użytkownik dostarczy** screenshoty w **5K rozdzielczości** dla każdej z gier (kilka na grę, różne sytuacje). Należy uwzględnić w planie testów. **Fixtures ścieżka:** `backend/tests/fixtures/images/poe2/*.png`, `backend/tests/fixtures/images/stellaris/*.png`. |
| 2 | Detekcja monitora gry | **`pygetwindow`** — biblioteka wykrywa aktywne okno gry, asystent capture z monitora na którym okno się znajduje. Fallback: `config.observer.monitor_index` (manual override). |
| 3 | OCR włączony domyślnie | **Wtedy kiedy potrzebny** — czyli per-game profile decyduje. Action games (PoE2) mają OCR włączony, strategy games (Stellaris) raczej nie. Konfigurowalny w `game_profile.ocr_enabled: true/false`. |

---

## DOK-10: MCP_TOOLS_SPEC.md

| # | Pytanie | Decyzja |
|---|---------|---------|
| 1 | Fallback dla SPA w `web_scraper` | **Playwright** (nie Selenium — Playwright jest nowszy, lżejszy, ma async-first API zgodne ze stackiem FastAPI). Aktywowany TYLKO gdy podstawowy scraper (httpx + trafilatura) zwróci pustą lub bardzo krótką treść. Konfigurowalny: `mcp.scraper.use_playwright_fallback: true/false`. Dependency: `playwright` + `playwright install chromium` (~300MB jednorazowo). |
| 2 | Web search backend | **DuckDuckGo** jako domyślny (`duckduckgo-search` library, zero setup). SearXNG jako opcjonalny advanced setup w sekcji "Migration / Advanced" w DOK-02 i DOK-10. |
| 3 | Nadpisywanie dokumentów | **Unikalne nazwy** — format: `{topic_slug}_{YYYY-MM-DD-HH.MM}.{ext}`. Przykład: `build_comparison_2026-04-27-14.32.html`. Brak overwrite — każde generowanie = nowy plik. |

---

## DOK-12: FRONTEND_SPEC.md

| # | Pytanie | Decyzja |
|---|---------|---------|
| 1 | Click-through toggle | **OBA** — komenda głosowa ("Pozwól mi klikać" / "Idź na bok") **i** hotkey/UI button. Stan persistowany w `system_state`. |
| 2 | Panel konfiguracji | **Osobne okno** Electron (BrowserWindow z `parent: avatarWindow`). Ma własne: title bar, size constraints, ikona w taskbar. Zamykany niezależnie od avatara. |
| 3 | Pobieranie modeli w Setup Wizard | **Background download** — nie blokuje wizardu. User może przejść kolejne kroki (audio, persona, test voice z wakeword) podczas gdy modele się ściągają. Wizard pokazuje progress bar. Test voice odbywa się po pobraniu STT/TTS (jedyny krok który czeka). |

---

## Decyzje implikowane (do uwzględnienia w dokumentach)

Z odpowiedzi wynikają dodatkowe decyzje implikowane:

### 1. **Konfiguracja imienia asystenta** (z DOK-02 #3)
Nowy klucz w `config.yaml`:
```yaml
general:
  assistant_name: "default_name"  # do listy w DOK-02
```
- Lista dostępnych imion = predefiniowane modele wakeword
- Zmiana imienia = swap modelu wakeword + restart wakeword detector
- Imię używane też w prompt builderze: "Jesteś asystentem o imieniu {assistant_name}"

### 2. **Hard Rule: Zero Halucynacji** (z DOK-05 #2)
To staje się **ósmą regułą architektoniczną** projektu, dopisana do PRD jako reguła naczelna. Wszystkie prompty (base, persona, observer comment) muszą ją zawierać. W DOK-13 (TEST_PLAN) dedykowane testy:
- "Zapytaj o nieistniejącą postać z gry" → expect "nie wiem" / propozycja wyszukania
- "Zapytaj o szczegół spoza knowledge base" → expect dopytanie o kontekst lub web_search

### 3. **Custom Commands → MCP** (z DOK-07 #3)
DOK-07 musi mieć rozszerzony schema `commands.yaml`:
```yaml
- id: weather_check
  triggers:
    - pattern: "sprawd\u017a pogod\u0119 w {city}"
      language: pl
  params:
    city:
      type: string
  action_type: mcp_tool_call
  action: web_search
  action_params:
    query: "pogoda {city} dzi\u015b"
  priority: 30
```

### 4. **Format nazw dokumentów** (z DOK-10 #3)
Konwencja w `c:\ai\asystent\documents\`:
- Pattern: `{type}_{topic_slug}_{YYYY-MM-DD-HH.MM}.{ext}`
- `topic_slug` = lowercase, podkreślniki zamiast spacji, max 40 chars
- Przykłady:
  - `report_session_summary_2026-04-27-22.15.md`
  - `comparison_lightning_arrow_vs_tornado_shot_2026-04-27-14.32.html`
  - `research_poe2_meta_season_2_2026-04-27-09.00.md`

### 5. **Two-window Architecture** (z DOK-12 #2)
Implikuje:
- Avatar window: frameless, transparent, AOT, narrow (np. 400×600)
- Config window: standard frame, resizable, normal z-order, ukrywany do tray
- IPC między oknami przez `ipcMain` w Electron (events: `config:save`, `avatar:reload`)
- Tray menu: "Pokaż awatar", "Pokaż ustawienia" jako dwie osobne akcje

### 6. **Background Model Download** (z DOK-12 #3)
Implikuje istnienie:
- Endpoint backend: `GET /setup/download_progress` → `{model_name, percent, eta_seconds}`
- WebSocket event: `download_progress` (server → client)
- Możliwość user-canceled download (graceful + cleanup partial files)
- Verification po pobraniu (SHA256 checksum z DOK-02)

### 7. **Atrybucja licencji CC-BY** (z DOK-02 #4)
Wybór modelu VRM z VRoid Hub na licencji CC-BY wymaga:
- Plik `c:\ai\asystent\LICENSES.md` z atrybucją autora modelu (imię, link do oryginału, licencja)
- Sekcja "Credits" w Config Panel (frontend) — widoczna lista wszystkich third-party assets z linkami
- README projektu z sekcją "Acknowledgements"
- Jeśli model jest swap'owany na własny → atrybucja pozostaje dla domyślnego (jest dostarczany w releasie)
- DOK-02 musi zawierać:
  - Wybrany model (nazwa, autor, URL VRoid Hub, hash pliku)
  - Backup model (drugi VRM na wypadek usunięcia oryginału)
  - Kryteria wyboru (rozmiar <30MB, pełne blendshapes, full humanoid)
  - Procedurę "audit licencji" przed each release (sprawdzenie czy model nadal dostępny + licencja niezmieniona)

---

## Reguły naczelne projektu (zaktualizowane po sesji)

Te reguły są nienegocjowalne i muszą być uwzględnione w **każdym** dokumencie:

1. **Offline-first** — core działa bez internetu (PRD)
2. **Sandbox twardy** — zero dostępu poza `c:\ai\asystent\` (PRD)
3. **Lokalność danych** — zero transmisji do chmury (PRD)
4. **Modulárność** — Strategy/Adapter pattern dla AI components (PRD)
5. **Polski domyślny** — z oryginalnymi tytułami (PRD)
6. **Awatar nigdy nie zamarza** — każdy stan ma wizualizację (PRD)
7. **User interaction priority** — PTT > observer (PRD)
8. **🆕 Zero halucynacji** — "nie wiem" jest poprawną odpowiedzią (DOK-05 #2)
9. **🆕 env > config** — zmienne środowiskowe override (DOK-03 #1)
10. **🆕 Komunikacja błędów głosem** — asystent informuje użytkownika audio (DOK-03 #2)

---

## Pytania pozostałe do follow-up

| Dokument | Pytanie | Status |
|----------|---------|--------|
| DOK-02 | Lista finalnych imion asystenta | ✅ Zamknięte 2026-04-30 |
| DOK-02 | Konkretny model VRM z VRoid Hub | ✅ Zamknięte 2026-04-30 |
| DOK-02 | Backup model VRM | ✅ Zamknięte 2026-04-30 |

---

## Finalizacja DOK-02 (sesja 2026-04-30)

### Imiona asystenta — lista finalna

**Imiona:** `Aria`, `Mira`, `Zara`, `Nova`, `Stella`, `Eve`

- Format wakeword: `"Hej {assistant_name}"` (np. "Hej Aria", "Hej Eve")
- Strategia wakeword: custom training openWakeWord dla każdego imienia z listy
- Fallback gdy custom training niemożliwy: prebuilt `"Hey Jarvis"` (openWakeWord posiada gotowy model)
- Config key: `general.assistant_name: "Aria"` (domyślne) + `general.wakeword_phrase: "Hej {assistant_name}"`
- Zmiana imienia w runtime: swap modelu wakeword + restart detektora (bez restartu backendu)

### Model VRM — primary i fallback

**Wybór:** Oficjalne sample avatary VRoid Team (pixiv), licencja CC0

- **Źródło:** hub.vroid.com — szukaj po autorze "VRoid Team" lub tagu "サンプル" / "sample"
- **Primary:** `models/avatar/primary.vrm` — żeński model anime, pełne blendshapes ARKit + VRM standard
- **Fallback:** `models/avatar/fallback.vrm` — drugi model z tego samego zestawu (inna fryzura/kolorystyka)
- **Kryteria weryfikacji modelu przed pobraniem:**
  - Rozmiar pliku: < 30MB
  - Licencja: CC0 lub CC-BY (widoczna na stronie modelu)
  - Blendshapes: pełen zestaw VRM Expression (happy, sad, angry, surprised, neutral) + ARKit (jeśli dostępne)
  - Bones: full humanoid (wymagane do animacji rąk/ciała)
  - Autor: VRoid Team / pixiv (najwyższe zaufanie do trwałości linku)
- **Atrybucja:** plik `c:\ai\asystent\LICENSES.md` — nazwa modelu, autor, URL, licencja CC0/CC-BY
- **Audit przed releasem:** sprawdzić czy URL modelu nadal aktywny + licencja niezmieniona

---

## Stan implementacji vs dokument (2026-05-09)

Ta sekcja utrzymuje zgodność między **decyzjami** a **kodem** (bez zmiany historycznych tabel powyżej).

| Obszar | Decyzja / zapis w tym pliku | Rzeczywista implementacja |
|--------|-----------------------------|---------------------------|
| Monitor gry | DOK-09: `pygetwindow` + fallback `observer.monitor_index` | Backend: `DesktopScreenCapture` (DXcam / mss / pyautogui) + **indeks monitora**; **brak `pygetwindow`**. Electron: wybór wyświetlacza dla overlaya (IPC). |
| Custom commands → MCP | Rozszerzenie `commands.yaml` (`action_type: mcp_tool_call`) | **Niewdrożone** w `backend/config` — brak pola `action_type` w schemacie custom komend. |
| Wizard: pobieranie modeli | `GET /setup/download_progress`, WS `download_progress`, cancel | **Endpointów downloadu w backendzie brak** — kreator zakłada istniejące ścieżki / konfigurację. |
| Quiet hours | Globalne (`general.quiet_hours` w CONFIG_SPEC) | `ConfigSchema`: **`quiet_hours_enabled`** + **`quiet_hours_start` / `quiet_hours_end`** (top-level). Runtime: wyciszenie TTS + overlay tekstu; status w `/api/v1/status` → `quiet_hours`. |
| Credits / CC-BY | Sekcja Credits w Config + `LICENSES.md` | `LICENSES.md` — tabela bundled VRM z `frontend/resources/`; w UI zakładka **Więcej** → sekcja Credits z odsyłaczem do pliku. |

**Niezmienione intencje:** env nadpisuje YAML, zero halucynacji w promptach, sandbox plików, offline-first, reguły PRD.

---

*Dokument referencyjny — załącz do każdego promptu DOK-01..DOK-16.*
