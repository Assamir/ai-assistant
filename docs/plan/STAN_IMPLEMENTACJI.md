# Stan implementacji — Assystent

> **Źródło prawdy:** ten plik zbiera **aktualny** obraz wdrożenia w kodzie (głównie `main`).  
> Szczegółowe kryteria akceptacji: [DEFINITION_OF_DONE.md](DEFINITION_OF_DONE.md).  
> Backlog niskiego priorytetu: [FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md).  
> **Ostatnia weryfikacja dokumentu:** 2026-05-09 (zsynchronizowano z `CHANGELOG.md` i strukturą repo).

Legenda stanu: **Gotowe** — działa w domyślnej ścieżce MVP przy poprawnej konfiguracji · **Częściowe** — w kodzie, wymaga opcji / modułów / env · **Backlog** — planowane (patrz IMP-xx) · **Poza kodem** — konfiguracja lub sprzęt użytkownika.

---

## 1. Obszary produktu

| Obszar | Stan | Krótki komentarz |
|--------|------|------------------|
| **Rdzeń backendu** (FastAPI, config Pydantic, `ASSY_*`, hot-reload) | Gotowe | Content root, YAML, `PUT /config` z tokenem opcjonalnym |
| **REST** (`/health`, `/status`, voice, player-profile, knowledge, daily-checks, …) | Gotowe | Agregacja zdrowia: `build_health_snapshot` + `health.overall` |
| **WebSocket** (`/ws`, multiple eventy, reconnect po stronie klienta) | Gotowe | m.in. `audio_stream`, `visual_state`, profil, cisza nocna |
| **Orkiestracja + komendy** | Gotowe | 22 reguły CMD (`command_matching.py`), emotion tag, narzędzia |
| **MCP + sandbox + cache** | Gotowe | `web_search` / `web_scraper` zawsze w rejestrze; `mcp.enabled` → gł. `generate_document` |
| **STT / TTS** | Częściowe / Poza kodem | Faster-Whisper / Piper — wymagają modeli i ścieżek w `content_root` |
| **PTT** | Gotowe | Frontend (pointer) + opcjonalnie backend `pynput`; WAV → `ptt_end` |
| **Zrzut ekranu** | Częściowe | DXcam → mss → pyautogui; `mss`+`pillow` w `requirements.txt` |
| **VLM / OCR / potok wizji** | Częściowe | Moondream / EasyOCR opcjonalne (`requirements-vision.txt`); pipeline = VLM i/lub OCR |
| **Obserwator + wykrywanie gry** | Gotowe | `GameObserver`, `ObserverLoop`, dHash, integracja z PTT; dźwięk powiadomienia opcjonalny |
| **Profil gracza, liga, daily meta, import buildu** | Gotowe | REST + WS; auto hint przy `game_detected` (flaga) |
| **Pamięć semantyczna (Chroma)** | Częściowe | Włączona `memory.enabled`; degradacja bez zależności |
| **SQLite + migracje** | Gotowe | `001` … `003` (`003` — wątki / agent); runner przy starcie |
| **Sesje, recovery, watchdog** | Gotowe | m.in. `recover_stale_sessions`, `SessionWatchdog` |
| **Cisza nocna** | Gotowe | `quiet_hours_*`, TTS/`audio_stream` wyciszone, overlay tekstowy (patrz CHANGELOG) |
| **Wątki rozmowy + narzędzia agenta** | Gotowe | `thread_manager`, `thread_tools`, `agent_tools`; UI: `ChatHistoryPanel` |
| **Frontend (Vite + React)** | Gotowe | Avatar VRM, emocje, lip-sync, czat, PTT, status z API |
| **Electron** | Gotowe | Overlay, tray, okno `#config`, IPC monitory, skróty (np. Ctrl+Shift+A/S) |
| **Instalatory Windows** | Gotowe | NSIS client / full (`electron-builder.*.yml`) |
| **Testy automatyczne** | Częściowe | Duży zestaw `pytest`; **brak** twardego progu pokrycia w CI |
| **Metryki wydajności (FPS, PTT→audio)** | Backlog | Szablon: [PERFORMANCE_BASELINE.md](PERFORMANCE_BASELINE.md); IMP-04 |

---

## 2. Zgodność z fazami roadmapy (wysoki poziom)

| Faza (DOK-16) | Tygodnie (plan historyczny) | Ocena wdrożenia w kodzie |
|---------------|-----------------------------|---------------------------|
| **1** Backend Core | T1–T4 | **Zamknięte funkcjonalnie** (szczegóły: DoD Faza 1) |
| **2** Vision, MCP, Memory | T5–T8 | **Zamknięte z zastrzeżeniem** modułów wizji opcjonalnych i voice→REST jako ścieżki dodatkowej (CMD/REST już częściowo pokrywają „asystenta”) |
| **3** Frontend + Avatar | T9–T14 | **Zamknięte** z drobnymi punktami DoD (Credits w panelu, test reconnect — opcjonalnie) |

Szczegółowy harmonogram tygodniowy (szacunki) pozostaje w [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) — to **plan pracy**, nie aktualny pomiar %.

---

## 3. Świadomie nie realizowane w tym repo (Decyzje)

| Temat | Uwaga |
|-------|--------|
| **Abstrakcja StorageBackend** | Dostęp przez repozytoria SQLite — patrz DoD |
| **Pełna auth poza tokenem `PUT /config`** | Backlog produktowy / IMP |
| **Custom komendy → bezpośrednie MCP** | IMP-01 |

---

## 4. Utrzymanie tego dokumentu

- Przy większych feature’ach: zaktualizuj **sekcję 1** i datę w nagłówku.
- Nie duplikuj tutaj pełnych list testów — odsyłaj do [TEST_PLAN.md](TEST_PLAN.md) i [DEFINITION_OF_DONE.md](DEFINITION_OF_DONE.md).
- Ryzyka projektowe bez zmian: [RISK_REGISTER.md](RISK_REGISTER.md).
