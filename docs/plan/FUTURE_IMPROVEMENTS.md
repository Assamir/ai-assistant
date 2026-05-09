# Przyszłe ulepszenia (backlog produktowy)

> **Cel dokumentu:** Szczegółowe karty ulepszeń niepriorytetyzowanych na bieżącą iterację release — ROI, zakres, koszt, wpływ.  
> **Powiązania:** [DECISIONS_LOG.md](../DECISIONS_LOG.md), [DEFINITION_OF_DONE.md](DEFINITION_OF_DONE.md), [implementation_plan_part2.md](implementation_plan_part2.md).

Legenda kosztu implementacji: **S** (≤1 dnia roboczego), **M** (2–5 dni), **L** (1–2 tygodnie), **XL** (>2 tygodnie), przy założeniu jednego dewelopera znanego z codebase.

---

## IMP-01 — Custom komendy → wywołanie narzędzia MCP (`commands.yaml`)

| Pole | Treść |
|------|--------|
| **ID** | IMP-01 |
| **Czego dotyczy** | Rozszerzenie konfiguracji komend użytkownika (`commands` w `config.yaml`) tak, aby dopasowanie głosowe / tekstowe mogło **bez LLM** wywołać zarejestrowane narzędzie MCP (np. `web_search`, `calculator`, `generate_document`) z parametrami zmapowanymi z grup regex lub slotów. |
| **Stan na dziś** | [`CommandSpec`](../../backend/config/schema.py) ma wyłącznie `name`, `description`, `params`, `aliases` — brak `action_type`, brak powiązania z [`ToolRegistry`](../../backend/mcp/registry.py). Custom komendy nie są opisane w [DECISIONS_LOG § Stan implementacji](../DECISIONS_LOG.md) jako wdrożone. |
| **Co wniesie** | Powtarzalne, deterministyczne skróty („Aria, policz …”, „wyszukaj build PoE …”) bez narzutu latencji LLM; możliwość udostępnienia społeczności gotowych fragmentów YAML; spójność z modelem „komenda najpierw, LLM potem”. |
| **ROI** | **Średni** dla power userów i konfiguracji wielokrotnego użytku; **niski** dla użytkownika domyślnego (22 wbudowane CMD już pokrywają większość ścieżek). Największy zwrot, gdy pojawi się wiele serwerów/narzędzi MCP lub integracje per gra. |
| **Przykłady** | Komenda `szukaj {query}` → `web_search` z `query=$1`. Komenda `zapisz notatkę {title}` → `generate_document` z szablonem MD (wymaga `mcp.enabled`). Komenda `rzut {sides}` → `dice_roll` bez zmiany promptów persony. |
| **Wpływ** | Backend: schema, loader konfiguracji, [`CommandMatcher`](../../backend/core/command_matching.py), dispatch obok [`dispatch_builtin`](../../backend/core/command_handlers.py), walidacja że narzędzie istnieje i argumenty spełniają JSON schema narzędzia; testy regresji kolejności dopasowań i cooldownów; dokumentacja DOK-07 / poradnik — **zakres szeroki**. Ryzyko: błędna konfiguracja YAML może wywołać nieoczekiwane narzędzia → potrzebna walidacja przy starcie (`PUT /config`). |
| **Szacowany koszt** | **L** (schema + matcher + handler + przykłady + testy ~15–40 plików dotkniętych selektywnie). Pełna obsługa slotów złożonych i warunków — zbliżenie do **XL**. |
| **Uwagi** | Rozważyć **whitelist** narzędzi dostępnych dla custom komend (np. tylko „bezpieczne”: `calculator`, `get_current_time`; bez `web_scraper` bez potwierdzenia). Spójność z [`mcp.tools_enabled`](../../backend/config/schema.py). Nie zastępuje function calling w czacie — uzupełnia go. |

---

## IMP-02 — Kreator startowy: pobieranie modeli i postęp (`download_progress`)

| Pole | Treść |
|------|--------|
| **ID** | IMP-02 |
| **Czego dotyczy** | Backendowy pipeline **pobierania** dużych artefaktów (modele Whisper / Piper / opcjonalnie VLM) z progressem: REST `GET /api/v1/setup/download_progress` (lub ścieżka pod `/setup/`), zdarzenie WebSocket `download_progress`, opcjonalnie anulowanie; integracja z [`SetupWizard.tsx`](../../frontend/src/SetupWizard.tsx) zamiast wyłącznie walidacji ścieżek. |
| **Stan na dziś** | Kreator zakłada istniejące pliki i konfigurację; zgodnie z [DECISIONS_LOG](../DECISIONS_LOG.md) **brak** endpointów downloadu w backendzie. |
| **Co wniesie** | Niższy próg wejścia dla użytkowników bez przyzwyczajenia do ręcznego wgrywania GB modeli; mniej błędów „ścieżka pusta”; możliwość dystrybucji **sprawdzonych** wersji modeli (hash, rozmiar). |
| **ROI** | **Wysoki** dla adopcji masowej / instalatora „full”; **niski**, jeśli docelowy użytkownik i tak trzyma modele w `content_root` z LM Studio. Zależy od polityki hostingu (CDN, koszt transferu, licencje modeli). |
| **Przykłady** | W kreatorze przycisk „Pobierz Whisper small” → pasek postępu w UI zsynchronizowany z WS; wznowienie po restarcie (`Range` / plik `.part`); checksum SHA256 przed aktywacją. |
| **Wpływ** | Nowy moduł serwisu (httpx/async file IO), miejsce docelowe pod `{content_root}`, konfiguracja listy artefaktów (URL, rozmiar, opcjonalny klucz licencyjny), bezpieczeństwo (TLS, weryfikacja podpisu lub hash z manifestu), frontend: hook + stan; dokumentacja [ENV_SETUP.md](../ENV_SETUP.md). Ryzyko: antywirus / SmartScreen blokujący pobieranie; odpowiedzialność za mirror pakietów. |
| **Szacowany koszt** | **XL** (pełny produkt: resume, cancel, manifest, testy integracyjne, migracja konfiguracji). **M** dla MVP bez resume — tylko jeden mały model i prosty procent z `httpx`. |
| **Uwagi** | Alternatywa przy niskim priorytecie: **tylko dokumentacja + skrypt PowerShell** pobierający z oficjalnych URL — bez integracji WS (częściowo spełnia IMP-02 bez kosztu XL). |

---

## IMP-03 — Quiet hours (cisza nocna) — pełna realizacja produktowa

| Pole | Treść |
|------|--------|
| **ID** | IMP-03 |
| **Czego dotyczy** | **Semantyka i enforce** pól [`quiet_hours_start` / `quiet_hours_end`](../../backend/config/schema.py) (HH:MM, przejście przez północ): kiedy wyciszyć TTS, kiedy przełączyć obserwatora na `text_overlay` lub pominąć komentarze, czy blokować powiadomienia dźwiękowe obserwatora ([`notification_sound`](../../CHANGELOG.md)). Ujednolicenie z dokumentacją CONFIG_SPEC (`general.quiet_hours` vs top-level — jedno źródło prawdy w kodzie i DOK-03). |
| **Stan na dziś** | Pola w schemacie **bez logiki runtime** w backendzie (wyjątek: testy konfiguracji). [DECISIONS_LOG § Stan implementacji](../DECISIONS_LOG.md) wymaga weryfikacji przed fazą release. |
| **Co wniesie** | Przewidywalne zachowanie w nocy (gracze, współlokatorzy); zgodność „to co ustawiam w YAML działa”; mniej zgłoszeń „dlaczego Aria nadal mówi o 2:00”. |
| **ROI** | **Wysoki** dla UX i zaufania do konfiguracji; **niski koszt** względem wartości przy wdrożeniu tylko helpera czasu + hook w orchestratorze / observerze. |
| **Przykłady** | `quiet_hours_start: "23:00"`, `quiet_hours_end: "07:00"` → po 23:00 odpowiedzi czatu nadal mogą iść na overlay zamiast TTS; obserwator: wyłączony ping + sam tekst; po 07:00 przywrócenie normalnego `audio_stream`. Wyjątek: jawna komenda „obudź się” / poza trybem snu już dziś zmienia stan — nie może kolidować z quiet hours bez decyzji produktowej. |
| **Wpływ** | Funkcja `_is_quiet_hours(now, tz)` współdzielona; wywołania przed [`speak`](../../backend/core/orchestrator.py) / ścieżkami TTS w [`observer_loop`](../../backend/services/observer_loop.py) / [`ws_router`](../../backend/api/ws_router.py); opcjonalnie synchronizacja z istniejącym `silent_mode` i `sleeping`; panel konfiguracji: krótki opis + time picker; [PORADNIK_UZYTKOWNIKA.md](../PORADNIK_UZYTKOWNIKA.md). |
| **Szacowany koszt** | **M** (logika czasu + integracja 3–5 punktów wyjścia audio + testy jednostkowe przypadków midnight + dokumentacja). **S**, jeśli tylko „feature flag: wyłączone” + komunikat w UI bez implementacji godzin. |
| **Uwagi** | Trzeba ustalić jedną regułę produktową: **A)** tylko TTS wyciszony, tekst i overlay działają; **B)** pełna cisza (brak komentarzy obserwatora); **C)** konfigurowalne podkluczem `observer.quiet_hours_behavior`. Rekomendacja z sesji planistycznej: **A lub C**. |

---

## IMP-04 — Metryki wydajności: FPS (< 5% wpływu), PTT → pierwsze audio (< 3 s)

| Pole | Treść |
|------|--------|
| **ID** | IMP-04 |
| **Czego dotyczy** | **Pomiar i utrzymanie** kryteriów z [DEFINITION_OF_DONE — Faza 1 §C](DEFINITION_OF_DONE.md): wpływ na FPS gry z włączonym asystentem vs bez; czas end-to-end od zwolnienia PTT do pierwszego chunka `audio_stream` (frontend + backend + LM Studio + TTS). Cele PRD: ok. < 5% FPS i < 3 s do pierwszego audio. |
| **Stan na dziś** | Punkty oznaczone jako niedokumentowane / niewymuszane w CI; smoke mock pipeline w backendzie nie zastępuje gry ani Electron. |
| **Co wniesie** | Obiektywna regresja przy zmianach (np. sentence-streaming TTS, DXcam); uzasadnienie priorytetów optymalizacji; zgodność z PRD dla „gaming companion”. |
| **ROI** | **Średni** dla maintainers (większość użytkowników nie mierzy sama); **wysoki** przy przygotowaniu materiałów marketingowych lub wersji „performance edition”. |
| **Przykłady** | Arkusz: gra (PoE2), rozdzielczość, tryb okna, FPS cap, **bez/z** overlayem + backend na tym samym PC; narzędzie: PresentMon / RTSS / wbudowany benchmark gry. PTT: timestamp `ptt_end` w frontendzie vs pierwszy `audio_stream` — log JSON lub telemetria developerska (tylko lokalnie). |
| **Wpływ** | Dokument `docs/plan/PERFORMANCE_BASELINE.md` (procedura); opcjonalnie skrypt Node/Python zbierający próby; **nie** jako twardy gate CI (zbyt zależny od sprzętu). Możliwa integracja z nightly **manual approval**. |
| **Szacowany koszt** | **M** dla dokumentu + 1–2 ręczne serie pomiarów i wpis do CHANGELOG; **L**, jeśli automatyczny harness (Electron + synthetic audio + mock LLM) na dedykowanym runnerze. |
| **Uwagi** | Rozdzielić: **latency backendu** (możliwa w CI z mockami) vs **latency pełna** (LM Studio + GPU — poza CI). Cel < 3 s jest **end-to-end** — bez kontroli nad modelem LLM użytkownika warto podawać „zakres typowy” i „worst case”. |

---

## Historia dokumentu

| Wersja | Data | Zmiany |
|--------|------|--------|
| 1.0 | 2026-05-09 | Utworzenie z kartami IMP-01 … IMP-04. |
