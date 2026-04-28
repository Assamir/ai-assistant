# PRD 03: Wymagania Niefunkcjonalne

> Część 3/6 — [Powrót do indeksu](PRD_00_INDEX.md)

---

## 1. Wydajność

| ID | Wymaganie | Wartość docelowa |
|----|-----------|-----------------|
| NF-P-01 | Opóźnienie end-to-end (mowa → odpowiedź audio) | < 3 sekundy |
| NF-P-01a | ↳ STT latency | < 0.5s |
| NF-P-01b | ↳ LLM time-to-first-token | < 0.5s |
| NF-P-01c | ↳ LLM full response | < 1.5s |
| NF-P-01d | ↳ TTS generation | < 0.5s |
| NF-P-02 | Wpływ na FPS (obserwator aktywny) | < 5% spadek |
| NF-P-03 | VRAM asystenta (bez LLM w LM Studio) | < 4 GB |
| NF-P-04 | Zużycie RAM | < 2 GB |
| NF-P-05 | Czas uruchomienia aplikacji | < 15 sekund |
| NF-P-06 | Czas odpowiedzi obserwatora (capture → komentarz) | < 5 sekund |

### 1.1 VRAM Budget (RTX 5090, 32 GB)

| Komponent | Szacowane VRAM |
|-----------|---------------|
| Gra (Stellaris / PoE2) | 4-8 GB |
| LLM — Gemma 4 E4B (LM Studio) | 12-16 GB |
| VLM — Moondream2 | ~1.5 GB |
| STT — Faster-Whisper (medium) | ~1 GB |
| TTS — Piper | ~0.5 GB (lub CPU) |
| OCR — EasyOCR | ~0.2 GB |
| **Razem** | **~19-27 GB** |
| **Zapas** | **5-13 GB** |

> [!WARNING]
> XTTSv2 (~1-2 GB) + LLaVA (~4 GB) zamiast Piper + Moondream2 mogą przekroczyć budżet przy wymagających grach. Domyślne modele: Piper + Moondream2.

### 1.2 GPU Scheduler

Mutex/semaphore kontrolujący dostęp do GPU — żadne dwa inference nie wykonują się równocześnie:

| Priorytet | Operacja | Uzasadnienie |
|-----------|----------|-------------|
| 1 (najwyższy) | STT (użytkownik mówi) | Responsywność interakcji |
| 2 | LLM (odpowiedź) | Użytkownik czeka |
| 3 | TTS (generowanie audio) | Może być na CPU |
| 4 (najniższy) | VLM (obserwator) | Nie jest time-critical |

### 1.3 Priorytety Wątków

| Komponent | Priorytet wątku (Windows) | Uzasadnienie |
|-----------|--------------------------|-------------|
| Audio capture / Wakeword | `NORMAL` | Real-time nasłuchiwanie |
| STT / LLM / TTS inference | `BELOW_NORMAL` | Nie rywalizuje z grą o CPU |
| Screen capture (DXcam) | `IDLE` | Najniższy, DXcam i tak jest szybki |
| Observer loop | `BELOW_NORMAL` | Background task |
| Daily check / Cleanup | `IDLE` | Background maintenance |

Implementacja: `SetThreadPriority` via `ctypes` lub `psutil`.

### 1.4 Performance Baseline Test

Obowiązkowy krok w Fazie 1:
1. Uruchom grę (Stellaris lategame, PoE2 mapping) **bez** asystenta → loguj FPS, CPU%, GPU%, VRAM co 1s
2. Uruchom z asystentem → loguj te same metryki
3. Porównaj → waliduj < 5% spadek FPS
4. Powtórz po każdej fazie jako regresja

---

## 2. Bezpieczeństwo i Prywatność

| ID | Wymaganie |
|----|-----------|
| NF-S-01 | Wszystkie dane przetwarzane lokalnie — zero transmisji do chmury (wyjątek: MCP web search gdy online) |
| NF-S-02 | Brak persystencji nagrań audio (usuwane z pamięci po transkrypcji) |
| NF-S-03 | Zrzuty ekranu usuwane z pamięci po analizie (wyjątek: debug mode) |
| NF-S-04 | **ZAKAZ** dostępu do schowka systemowego |
| NF-S-05 | **ZAKAZ** dostępu do ustawień systemu operacyjnego |
| NF-S-06 | **ZAKAZ** dostępu do dysku poza content root (`c:\ai\asystent`) |
| NF-S-07 | Detekcja procesu gry: wyłącznie read-only `process.name()` |

### 2.1 Sandbox — Dozwolone vs. Zabronione

| ✅ DOZWOLONE | ❌ ZABRONIONE |
|-------------|--------------|
| Odczyt/zapis w `c:\ai\asystent\**` | Dowolna inna ścieżka na dysku |
| Odczyt nazwy aktywnego procesu | Ingerencja w procesy użytkownika |
| Przechwytywanie ekranu (read-only pixel data) | Dostęp do schowka |
| Wyszukiwanie w internecie (MCP, gdy online) | Modyfikacja ustawień Windows |
| Nagrywanie audio z mikrofonu (za zgodą) | Dostęp do rejestru systemowego |
| Odtwarzanie audio przez głośniki | Instalacja sterowników/pakietów systemowych |

Whitelist ścieżek w warstwie MCP — każdy tool I/O sprawdza czy ścieżka jest w `c:\ai\asystent\`.

---

## 3. Kompatybilność

| ID | Wymaganie |
|----|-----------|
| NF-C-01 | System operacyjny: Windows 10/11 (x64) |
| NF-C-02 | GPU: NVIDIA RTX 30xx+ (z obsługą CUDA) |
| NF-C-03 | Wymagany LM Studio zainstalowany z załadowanym modelem |
| NF-C-04 | Python 3.10+ |
| NF-C-05 | Node.js 18+ (dla Electron) |

---

## 4. Jakość Kodu i Utrzymanie

| ID | Wymaganie |
|----|-----------|
| NF-Q-01 | Architektura modułowa — wzorzec Strategy/Adapter dla komponentów AI |
| NF-Q-02 | Interfejsy: `BaseLLMClient`, `BaseSTTEngine`, `BaseTTSEngine`, `BaseVLMAnalyzer`, `StorageBackend` |
| NF-Q-03 | API backendu dokumentowane (auto-docs FastAPI / Swagger) |
| NF-Q-04 | Testy jednostkowe z mockami (80%+ coverage logiki backendu) |
| NF-Q-05 | Config hot-reload dla personas, game profiles, commands |
| NF-Q-06 | Wymiana modelu AI = zmiana konfiguracji + ewentualny nowy adapter (bez zmian w orkiestratorze) |

### 4.1 Hot-Reload vs. Restart

| Zmiana | Hot-reload ✅ | Restart wymagany 🔄 |
|--------|-------------|-------------------|
| Persona (.md) | ✅ | |
| Game profile (.yaml) | ✅ | |
| Commands (.yaml) | ✅ | |
| Debug flag | ✅ | |
| Observer interval | ✅ | |
| Models path | | 🔄 |
| Audio devices | | 🔄 |
| Storage backend | | 🔄 |

File watcher (`watchdog` library) na katalog `config/` i `personas/`. Asystent informuje: „Zauważyłem zmianę konfiguracji, przeładowałem."

---

## 5. Logowanie i Diagnostyka

### 5.1 Session Transcripts

Format: Markdown z timestampami i tagami:
```markdown
## Sesja 2026-04-25 18:30 - 22:15

[18:30:15] [SYSTEM] Asystent uruchomiony. Tryb: Healthy. Internet: dostępny.
[18:31:02] [USER] Hej, co nowego w meta PoE2?
[18:31:04] [ASSISTANT] [EMO:amused] Od ostatniego sprawdzenia Lightning Arrow dostał buff...
[18:45:12] [OBSERVER] Wykryto grę: PathOfExile_x64.exe → profil poe2
[18:45:18] [OBSERVER] Scena: Gracz w Act 3, walka z grupą mobów
[18:45:20] [ASSISTANT] [EMO:excited] Uważaj na tego rzadkiego moba po lewej!
```

- Pliki per sesja: `logs/sessions/YYYY-MM-DD_sessionN.md`
- Konfigurowalny: `log_observer_comments: true/false`
- Kompresja logów starszych niż 30 dni → `.7z` (via `py7zr`, fallback `.zip`)

### 5.2 Debug Mode

Flaga w `config.yaml` → `debug.enabled: true`:

| Funkcja | Opis |
|---------|------|
| Zapis zrzutów ekranu | `debug/screenshots/` z timestampem |
| Log pipeline | raw audio → STT → LLM prompt → response → emotion → TTS params |
| Endpoint `GET /debug/last_interaction` | Pełny pipeline jako JSON |
| Overlay tekstowy na awatarze | Aktualny stan: „STT processing…", „LLM generating…" |

W trybie release: wszystko wyłączone, zero narzutu.

### 5.3 System Status Log

Plik `logs/system_status.log` aktualizowany co 60 sekund + endpoint `GET /status`:
- VRAM usage, CPU%, RAM
- Aktywne wątki, stan obserwatora
- Last daily check, cache size
- Circuit breaker state

---

*Następny dokument: [PRD 04: Architektura i Tech Stack](PRD_04_ARCHITECTURE.md)*
