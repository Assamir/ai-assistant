# PRD 02: Wymagania Funkcjonalne

> Część 2/6 — [Powrót do indeksu](PRD_00_INDEX.md)

---

## 1. Awatar 3D (Nakładka)

| ID | Wymaganie | Priorytet | Akceptacja |
|----|-----------|-----------|------------|
| F-AV-01 | Ładowanie i renderowanie modeli `.vrm` | **Must** | Model VRM wyświetla się poprawnie |
| F-AV-02 | Always-on-Top z konfigurowalną przezroczystością | **Must** | Widoczny nad grą (borderless) |
| F-AV-03 | Skalowanie i repozycjonowanie (drag & drop) | **Should** | Zmiana rozmiaru/pozycji w UI |
| F-AV-04 | Lip-sync zsynchronizowany z TTS audio | **Must** | Usta poruszają się w rytm mowy |
| F-AV-05 | Animacje idle (mruganie, oddychanie, ruchy) | **Should** | Awatar nie jest zamrożony |
| F-AV-06 | Zmiana modelu VRM w runtime | **Should** | Z poziomu panelu konfiguracji |
| F-AV-07 | 16 stanów emocjonalnych z unikalnymi animacjami | **Must** | Każda emocja ma odrębną ekspresję |
| F-AV-08 | Stany wizualne systemu (listening, thinking, error) | **Must** | Użytkownik widzi stan asystenta |
| F-AV-09 | Domyślny model VRM dostarczony z aplikacją | **Must** | Stylizowany anime, darmowa licencja |
| F-AV-10 | Trójwarstwowy fallback emocji (blendshapes → aura → body) | **Should** | Emocje działają na modelach z ograniczonymi blendshapes |

### 1.1 Lista Emocji (16)

| Kategoria | Emocje |
|-----------|--------|
| **Pozytywne** | `happy`, `amused`, `proud`, `sympathetic` |
| **Negatywne** | `sad`, `disappointed`, `angry`, `disgusted` |
| **Energetyczne** | `excited`, `scared`, `surprised`, `nervous` |
| **Refleksyjne** | `thinking`, `confused`, `nostalgic`, `sarcastic` |

Każda emocja mapuje się na:
- **Blendshapes VRM** — wyrażenie twarzy (jeśli model wspiera)
- **Aura/shader** — kolor poświaty (niezależna od modelu)
- **Body animation** — proceduralne gesty w Three.js (rotacje kości, oscylacje)
- **Modulacja TTS** — speed i pitch (np. excited → 1.2x speed, +10% pitch)

### 1.2 Stany Wizualne Systemu

| Stan | Wizualizacja |
|------|-------------|
| Idle | Normalne animacje idle |
| Listening (PTT/wakeword) | Zielona poświata |
| Thinking (LLM processing) | Pulsująca aura, animacja zamyślenia |
| Speaking | Lip-sync + jaśniejszy awatar |
| Error | Czerwona poświata, emocja `sad` |
| Degraded (brak LLM) | Żółta poświata, emocja `sad` + statusowa kropka |

### 1.3 Animacje Proceduralne

Generowane kodem w Three.js (nie pliki zewnętrzne):
- Rotacje kości przez `VRMHumanoid` API (head tilt, body lean)
- Sinusoidalne oscylacje parametryzowane per emocja (oddychanie, kołysanie)
- Jednorazowe akcenty (podskoczenie = translate Y + spring-back, cofnięcie = translate Z + head tilt back)
- Skan dostępnych blendshapes przy ładowaniu modelu → auto-mapowanie emocji

---

## 2. Komunikacja Głosowa

| ID | Wymaganie | Priorytet | Akceptacja |
|----|-----------|-----------|------------|
| F-VO-01 | Push-to-Talk (PTT) pod konfigurowalnym klawiszem/przyciskiem myszy | **Must** | Przytrzymanie → nagrywanie → zwolnienie → przetwarzanie |
| F-VO-02 | Ciągłe nasłuchiwanie z wakewordem (np. „Hej Asystent") | **Must** | Wakeword → aktywacja nagrywania |
| F-VO-03 | Przełączanie PTT ↔ Wakeword bez restartu | **Must** | Zmiana z UI lub komendy głosowej |
| F-VO-04 | STT (Faster-Whisper) z confidence threshold | **Must** | Rozpoznawanie PL + EN; próg pewności |
| F-VO-05 | TTS z naturalnym głosem i modulacją emocji | **Must** | Płynne audio z variacją speed/pitch per emocja |
| F-VO-06 | Wybór mikrofonu (wejście) z UI | **Should** | Lista urządzeń audio |
| F-VO-07 | Wybór głośników (wyjście) z UI | **Should** | Lista urządzeń wyjściowych |
| F-VO-08 | Audio duck — PTT natychmiast wycisza TTS (<200ms) | **Must** | Odpowiedź użytkownika ma priorytet |
| F-VO-09 | Dźwięk powiadomienia przed komentarzem obserwatora | **Should** | Subtelny ping, konfigurowalny |
| F-VO-10 | Tryb cichy — TTS → overlay tekstowy obok awatara | **Should** | Komenda „Wycisz się" |
| F-VO-11 | Konfigurowalny wakeword | **Could** | Zmiana słowa wybudzającego |

### 2.1 STT Confidence Threshold

| Confidence | Zachowanie |
|------------|------------|
| > 0.7 | Normalne przetwarzanie |
| 0.4 — 0.7 | „Nie jestem pewien czy dobrze usłyszałem: *[transkrypcja]*. Czy o to chodziło?" |
| < 0.4 | „Przepraszam, nie zrozumiałem. Możesz powtórzyć?" + emocja `confused` |

Progi konfigurowalne w `config.yaml` → `audio.stt_confidence_threshold`.

### 2.2 Logika Priorytetów Audio

1. **Interakcja użytkownika** (PTT/wakeword) → zawsze najwyższy priorytet
2. Komentarz obserwatora **wstrzymywany/anulowany** gdy wykryto mowę
3. Audio duck: głośność TTS → 0% w <200ms przy aktywacji PTT
4. Po zakończeniu odpowiedzi użytkownikowi → pętla obserwatora wznawia

---

## 3. Silnik AI / LLM

| ID | Wymaganie | Priorytet | Akceptacja |
|----|-----------|-----------|------------|
| F-AI-01 | Integracja z LM Studio (OpenAI-compatible API) | **Must** | Poprawne wysyłanie promptów i odpowiedzi |
| F-AI-02 | Gemma 4 E4B jako domyślny LLM | **Must** | Sensowne odpowiedzi |
| F-AI-03 | Kontekstowe zarządzanie historią konwersacji | **Must** | Pamięta kontekst w sesji |
| F-AI-04 | Konfigurowalne osobowości (persony) via pliki .md | **Must** | Zmiana tonu/stylu z pliku |
| F-AI-05 | Streaming odpowiedzi (token-by-token) | **Should** | TTS zaczyna przed zakończeniem generowania |
| F-AI-06 | Function calling (OpenAI-compatible tool use) | **Must** | LLM sam decyduje o użyciu MCP tools |
| F-AI-07 | Inline emotion tags `[EMO:nazwa]` w odpowiedziach | **Must** | Tag parsowany, usuwany przed TTS |
| F-AI-08 | Dynamiczne łączenie promptów | **Must** | base + persona + [observer_context] + [game_profile] |

### 3.1 System Promptów

Prompt składany dynamicznie:
```
[BASE_SYSTEM_PROMPT]          — reguły ogólne, język, emocje
+ [PERSONA_PROMPT]            — z pliku personas/*.md
+ [GAME_PROFILE_CONTEXT]      — jeśli wykryto grę (z game_profiles/*.yaml)
+ [OBSERVER_CONTEXT]          — jeśli obserwator aktywny (opis ostatniej sceny)
+ [PLAYER_PROFILE]            — aktywna postać, build, liga
+ [LANGUAGE_INSTRUCTION]      — reguła językowa PL/EN
```

---

## 4. Tryb Obserwatora

| ID | Wymaganie | Priorytet | Akceptacja |
|----|-----------|-----------|------------|
| F-OB-01 | Przechwytywanie ekranu DXcam z min. wpływem na FPS | **Must** | Brak zauważalnego spadku FPS |
| F-OB-02 | Analiza VLM (Moondream2/LLaVA) zrzutów ekranu | **Must** | Poprawny opis sceny |
| F-OB-03 | Pipeline OCR dla drobnego tekstu UI (itemy, statystyki) | **Should** | Ekstrakcja affixów, tierów, DPS |
| F-OB-04 | Pętla obserwatora: Capture → VLM → [OCR] → LLM → TTS | **Must** | Autonomiczne komentarze |
| F-OB-05 | Konfigurowalny interwał (5s, 10s, 30s) | **Should** | Wybór w UI |
| F-OB-06 | Start/stop komendą głosową lub klawiszem | **Must** | „Zacznij/Przestań obserwować" |
| F-OB-07 | Detekcja zmian na ekranie (unikanie analizy statycznych scen) | **Could** | Analiza tylko przy istotnej zmianie |
| F-OB-08 | On-demand Screen Query (jednorazowy capture na pytanie) | **Must** | „Co widzisz na ekranie?" → single-shot |
| F-OB-09 | Kontekst pozycji kursora przy on-demand query | **Should** | Full screenshot + crop 600x400 wokół kursora |
| F-OB-10 | Auto-detekcja gry (kaskadowa) | **Must** | Proces → VLM fallback → ręczne nadpisanie |

### 4.1 Typy Obserwatora

| Typ | Trigger | Zachowanie |
|-----|---------|------------|
| **Game Observer** | Wykryto proces gry + komenda „Obserwuj" | Pętla co N sekund, pełna analiza |
| **On-demand Query** | Pytanie o ekran: „Co tu widzisz?" | Jednorazowy capture + analiza, brak pętli |
| **Ambient Observer** | Pytanie o ekran poza grą | Jednorazowy capture (jak on-demand), wyłączony domyślnie |

### 4.2 Profile Gier

Format: YAML w `config/game_profiles/`

```yaml
# config/game_profiles/poe2.yaml
name: "Path of Exile 2"
process_names: ["PathOfExile_x64.exe", "PathOfExileSteam.exe"]
observer_type: action
observer_interval_seconds: 5
focus_areas: [builds, loot, combat, boss_mechanics]
screen_regions:
  - name: "health_mana"
    position: "bottom-left"
    size: "15%"
  - name: "minimap"
    position: "top-right"
    size: "15%"
context_prompt: |
  Jesteś ekspertem od Path of Exile 2. Skupiaj się na:
  - Analizie przedmiotów (affixy, tier, wartość)
  - Ostrzeganiu przed niebezpieczeństwami
  - Sugestiach dotyczących buildu gracza
mcp_sources: ["poe2 wiki", "maxroll.gg/poe2"]
```

### 4.3 Pipeline VLM + OCR (Dual)

```
Capture ekranu (DXcam)
       │
       ├─→ VLM (Moondream2): analiza ogólna sceny
       │       "Gracz w inventory, patrzy na item"
       │
       └─→ Jeśli wykryto tooltip/item:
               Crop regionu → OCR (Tesseract/EasyOCR)
               "Adds 45-78 Lightning Damage, Tier 2"
       │
       └─→ Oba wyniki → LLM → komentarz/rada
```

---

## 5. MCP Tools

| # | Tool | Opis | Limit |
|---|------|------|-------|
| 1 | `web_search` | Wyszukiwanie DuckDuckGo/SearXNG | Rate limit: 10 req/min |
| 2 | `web_scraper` | Pobranie i parsowanie URL do tekstu | Cache TTL: 7 dni |
| 3 | `get_current_time` | Zwraca `datetime.now()` | Bez limitu |
| 4 | `calculator` | Bezpieczne obliczenia (asteval) | Bez limitu |
| 5 | `generate_document` | Generowanie MD/HTML dokumentów | Bez limitu |
| 6 | `screen_capture` | Jednorazowy capture + analiza (on-demand) | Bez limitu |

### 5.1 Function Calling

Każdy tool zdefiniowany jako JSON schema (OpenAI-compatible). LLM sam decyduje kiedy i które narzędzie wywołać. Fallback: jeśli model nie wspiera function calling → instrukcje w system prompcie.

**Limit:** `max_tool_calls_per_turn: 5` (konfigurowalny). Po osiągnięciu → LLM odpowiada na bazie zebranych danych. `generate_document` nie liczy się do limitu.

### 5.2 Cache MCP

| Typ zapytania | TTL Cache |
|---------------|-----------|
| Game meta (buildy, patche) | 24 godziny |
| Ogólne zapytania | 1 godzina |
| Strony (web scraper) | 7 dni |

Cache w `data/mcp_cache/` (SQLite). Komenda „Odśwież informacje o X" → bypass cache. Cleanup: automatyczny przy starcie.

### 5.3 Rate Limiter

Max 10 requestów/minutę do web search. Jeśli rate limited → emocja `disappointed`, komunikat „Nie mogę teraz szukać, spróbuję później."

---

## 6. Pamięć i Persystencja

| ID | Wymaganie | Priorytet | Akceptacja |
|----|-----------|-----------|------------|
| F-ME-01 | Historia konwersacji w SQLite (Repository Pattern) | **Must** | Pamięć między sesjami |
| F-ME-02 | Pamięć semantyczna (ChromaDB/LanceDB) do recall kontekstu | **Should** | Przywołanie relevantnych wspomnień |
| F-ME-03 | Profil gracza (YAML) z wieloma postaciami per gra | **Must** | Pamiętanie buildu, klasy, ligi |
| F-ME-04 | Konfigurowalny backend storage (SQLite → Postgres → GCP) | **Should** | Interfejs `StorageBackend` |
| F-ME-05 | Auto-archiwizacja konwersacji starszych niż N dni (domyślnie 90) | **Should** | Kompresja do .7z |
| F-ME-06 | Limit pamięci semantycznej (10 000 embeddingów) | **Should** | Rotacja najstarszych |
| F-ME-07 | Komenda „Zapomnij o X" do ręcznego usuwania | **Could** | Usunięcie z bazy |
| F-ME-08 | Backup/restore jednym poleceniem | **Should** | Zip całego content root |

### 6.1 Profil Gracza

```yaml
# data/player_profile.yaml
games:
  poe2:
    active_character: "SparkyBoy"
    league: "Season 2"
    characters:
      - name: "SparkyBoy"
        class: "Deadeye"
        build: "Lightning Arrow"
        level: 87
        build_url: "https://maxroll.gg/poe2/..."
        notes: "Potrzebuje lepszego łuku"
      - name: "TankMaster"
        class: "Marauder"
        build: "Slam Juggernaut"
        level: 42
    last_meta_check: "2026-04-25"
  stellaris:
    active_empire: "Zjednoczona Federacja"
    game_version: "3.12"
```

Komenda: „Gram teraz TankMasterem" → zmiana `active_character`.

Import buildu z URL: użytkownik podaje URL (np. maxroll.gg) → MCP `web_scraper` pobiera stronę → LLM wyciąga dane buildu → zapis do profilu. **Fallback:** jeśli strona wymaga JavaScript (SPA) i scraper nie działa → asystent pyta użytkownika o dane buildu konwersacyjnie.

### 6.2 Daily Meta Check

Przy starcie asystenta, jeśli od ostatniego checku >24h:
1. Low-priority thread uruchamia MCP `web_search` z zapytaniem o aktualne buildy
2. Porównuje z zapamiętanym buildem gracza
3. Zapisuje wyniki do `knowledge/` (local knowledge base)
4. Przy kolejnej rozmowie proaktywnie: „Hej, od ostatniego sprawdzenia pojawiły się zmiany w meta — chcesz posłuchać?"
5. Konfigurowalny: `daily_check_on_startup: true/false`

### 6.3 Reset Sezonowy

Jeśli MCP wykryje nowy sezon (np. PoE2 liga):
- Asystent **pyta**: „Wygląda na to, że wystartował nowy sezon. Chcesz zresetować profil buildu?"
- Stary profil → `data/archive/poe2_season_X.yaml`
- **Nigdy** nie kasuje automatycznie

---

## 7. Generowanie Dokumentów

| ID | Wymaganie | Priorytet | Akceptacja |
|----|-----------|-----------|------------|
| F-DOC-01 | Generowanie dokumentów Markdown na żądanie | **Must** | „Napisz raport o X" → plik .md |
| F-DOC-02 | Generowanie single-file HTML z inline CSS | **Should** | Ciemny motyw, typografia, print-ready |
| F-DOC-03 | Diagramy Mermaid.js w HTML | **Should** | Interaktywne diagramy w jednym pliku |
| F-DOC-04 | Tabele, formatowanie, strukturalne dane | **Must** | Raporty z tabelami porównawczymi |
| F-DOC-05 | Auto-raport z sesji gamingowej | **Could** | Po zamknięciu gry, konfigurowalny |
| F-DOC-06 | Dwuwarstwowa odpowiedź: głos (synteza) + plik (dane) | **Must** | Głosowo: podsumowanie. Plik: pełne dane |

### 7.1 Typy Dokumentów

| Typ | Trigger | Zawartość |
|-----|---------|-----------|
| Raport z sesji | Komenda „Podsumuj sesję" lub auto po grze | Czas gry, key moments, rady, itemy |
| Raport z researchu | „Porównaj buildy LA vs TS" | Wyniki MCP, tabele porównawcze |
| Dowolny dokument | „Napisz raport o X" | LLM generuje treść |

### 7.2 Template HTML

Plik `templates/report_template.html`:
- Ciemny motyw (spójny z estetyką asystenta)
- Typografia: Inter/Roboto (Google Fonts CDN, offline fallback base64)
- `@media print` dla drukowania
- Mermaid.js CDN dla diagramów (offline: code block fallback)
- Konfigurowalny: `documents.html_theme: dark | light`

Zapis do `documents/` z automatyczną nazwą: `[typ]_[data]_[temat].md|html`

---

## 8. Konfiguracja i UI

| ID | Wymaganie | Priorytet | Akceptacja |
|----|-----------|-----------|------------|
| F-UI-01 | Panel konfiguracji ukrywalny (hotkey) | **Must** | Bez przeszkadzania w grze |
| F-UI-02 | Wybór monitora (multi-monitor) | **Should** | Awatar na wybranym monitorze |
| F-UI-03 | Ustawienia audio (mikrofon, głośniki, głośność TTS) | **Should** | Konfiguracja urządzeń |
| F-UI-04 | Wybór modelu VRM | **Should** | Zmiana awatara z UI |
| F-UI-05 | System tray z menu (Start/Stop/Restart/Settings/Quit) | **Must** | Ikona w zasobniku |
| F-UI-06 | Globalny hotkey `Ctrl+Shift+A` — toggle widoczności | **Should** | Ukryj/pokaż awatar |
| F-UI-07 | Zakładka „Status" z metrykami systemu | **Should** | VRAM, wątki, stan obserwatora |
| F-UI-08 | Komendy głosowe „Idź spać" / „Obudź się" | **Must** | Toggle bez zamykania backendu |

---

## 9. Komendy Systemowe

### 9.1 Wbudowane Komendy (bez LLM)

Przetwarzane **przed** wysłaniem do LLM (regex pattern matching):

| Komenda | Akcja |
|---------|-------|
| „Idź spać" | Ukryj awatar, stop obserwator, wakeword aktywny |
| „Obudź się" | Przywróć awatar |
| „Zacznij obserwować" | Start game observer loop |
| „Przestań obserwować" | Stop observer loop |
| „Wycisz się" | TTS → overlay tekstowy |
| „Możesz mówić" | Powrót z trybu cichego do normalnego TTS |
| „Zrób backup" | Zip content root → backups/ |
| „Podsumuj sesję" | Generuj raport z sesji |
| „Otwórz dokumenty" | Otwiera folder `documents/` w eksploratorze Windows |
| „Przeładuj konfigurację" | Hot-reload config |
| „Ustaw interwał na {N} sekund" | Zmiana observer_interval |
| „Zmień personę na {nazwa}" | Przeładuj system prompt |
| „Gram teraz {postacią}" | Zmiana active_character |

### 9.2 Custom Komendy

Definiowane w `config/commands.yaml`:
```yaml
- trigger: ["ustaw interwał na {value} sekund"]
  action: set_observer_interval
  params: { interval: "{value}" }
- trigger: ["zmień personę na {name}", "bądź {name}"]
  action: change_persona
  params: { persona: "{name}" }
```

Parser: regex z named groups. Brak dopasowania → forward do LLM.

---

*Następny dokument: [PRD 03: Wymagania Niefunkcjonalne](PRD_03_NONFUNCTIONAL.md)*
