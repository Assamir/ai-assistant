# PRD: Lokalny Asystent Gracza AI

> **Status:** Draft v0.1 — do przeglądu w sesji planistycznej  
> **Data:** 2026-04-25  
> **Autor:** Zespół Assystent  

---

## 1. Podsumowanie Produktu

### 1.1 Wizja
Lokalny, w pełni prywatny asystent AI z trójwymiarowym awatarem, który towarzyszy użytkownikowi podczas korzystania z komputera — w szczególności podczas sesji gamingowych. Asystent komunikuje się głosowo, analizuje obraz na ekranie w czasie rzeczywistym i autonomicznie komentuje rozgrywkę, działając jak inteligentny kompan oparty o modele AI uruchamiane lokalnie.

### 1.2 Problem
- Istniejące asystenty AI (Copilot, Alexa, Google Assistant) wymagają chmury — brak prywatności i zależność od internetu.
- Brak dedykowanych asystentów gamingowych z wizją (analizą ekranu) i autonomicznym komentowaniem.
- Dostępne rozwiązania nie oferują immersyjnej prezencji (awatar 3D nakładany na ekran gry).

### 1.3 Grupa Docelowa
- Gracze PC z wydajnym sprzętem (RTX 5090 lub porównywalna karta GPU).
- Użytkownicy ceniący prywatność i lokalność przetwarzania AI.
- Entuzjaści AI chcący eksperymentować z lokalnymi modelami LLM/VLM.

### 1.4 Kluczowe Cele Biznesowe
| # | Cel | Metryka sukcesu |
|---|-----|-----------------|
| C1 | Działanie w pełni lokalne (offline-first) | 100% funkcjonalności bez połączenia z internetem |
| C2 | Minimalne obciążenie systemu podczas gry | < 5% spadek FPS przy włączonym asystencie |
| C3 | Naturalna interakcja głosowa | Czas odpowiedzi (end-to-end) < 3 sekundy |
| C4 | Użyteczne komentarze do rozgrywki | Pozytywna ocena subiektywna użytkownika |

---

## 2. Wymagania Funkcjonalne

### 2.1 Awatar 3D (nakładka)

| ID | Wymaganie | Priorytet | Akceptacja |
|----|-----------|-----------|------------|
| F-AV-01 | System ładuje i renderuje modele w formacie `.vrm` | **Must** | Model VRM wyświetla się poprawnie na ekranie |
| F-AV-02 | Awatar jest wyświetlany jako nakładka Always-on-Top z konfigurowalną przezroczystością | **Must** | Awatar widoczny nad grą w trybie pełnoekranowym (borderless) |
| F-AV-03 | Użytkownik może skalować i repozycjonować awatar (drag & drop) | **Should** | Zmiana rozmiaru i pozycji przez UI |
| F-AV-04 | Lip-sync — animacja ust zsynchronizowana z odtwarzanym audio TTS | **Must** | Usta poruszają się w rytm mowy |
| F-AV-05 | Animacje idle (mruganie, oddychanie, drobne ruchy) | **Should** | Awatar nie jest „zamrożony" w bezruchu |
| F-AV-06 | Użytkownik może zamieniać model VRM w runtime | **Could** | Zmiana modelu z poziomu panelu konfiguracji |

### 2.2 Komunikacja Głosowa

| ID | Wymaganie | Priorytet | Akceptacja |
|----|-----------|-----------|------------|
| F-VO-01 | Tryb Push-to-Talk (PTT) pod konfigurowalnym klawiszem lub przyciskiem myszy | **Must** | Przytrzymanie przycisku → nagrywanie → zwolnienie → przetwarzanie |
| F-VO-02 | Tryb ciągłego nasłuchiwania ze słowem wybudzającym (wakeword) | **Must** | Powiedzenie „Hej Asystent" → aktywacja nagrywania |
| F-VO-03 | Przełączanie między trybami PTT ↔ Wakeword bez restartu | **Must** | Zmiana trybu z poziomu UI lub komendy głosowej |
| F-VO-04 | Transkrypcja mowy (STT) z użyciem Faster-Whisper | **Must** | Rozpoznawanie mowy w języku polskim i angielskim |
| F-VO-05 | Synteza mowy (TTS) z naturalnie brzmiącym głosem | **Must** | Audio generowane i odtwarzane płynnie |
| F-VO-06 | Wybór urządzenia wejściowego (mikrofonu) z poziomu UI | **Should** | Lista dostępnych urządzeń audio z możliwością wyboru |
| F-VO-07 | Konfigurowalny wakeword | **Could** | Użytkownik może zmienić słowo wybudzające |

### 2.3 Silnik AI / LLM

| ID | Wymaganie | Priorytet | Akceptacja |
|----|-----------|-----------|------------|
| F-AI-01 | Integracja z LM Studio przez API kompatybilne z OpenAI | **Must** | Poprawne wysyłanie promptów i odbieranie odpowiedzi |
| F-AI-02 | Obsługa modelu Gemma 4 E4B jako domyślnego LLM | **Must** | Model odpowiada sensownie na pytania użytkownika |
| F-AI-03 | Kontekstowe zarządzanie historią konwersacji | **Must** | Asystent pamięta kontekst w ramach sesji |
| F-AI-04 | System promptów z konfigurowalnymi osobowościami | **Should** | Możliwość zdefiniowania tonu i stylu asystenta |
| F-AI-05 | Streaming odpowiedzi (token-by-token) dla responsywnego TTS | **Should** | Odpowiedź zaczyna być odtwarzana zanim zakończy się generowanie |

### 2.4 Tryb Obserwatora (Analiza Rozgrywki)

| ID | Wymaganie | Priorytet | Akceptacja |
|----|-----------|-----------|------------|
| F-OB-01 | Przechwytywanie ekranu z użyciem DXcam z minimalnym wpływem na FPS | **Must** | Zrzuty ekranu bez spadku FPS w grze |
| F-OB-02 | Analiza zrzutów ekranu lokalnym modelem VLM (Moondream2 / LLaVA) | **Must** | Model poprawnie opisuje scenę z gry |
| F-OB-03 | Pętla obserwatora: Zrzut → VLM → Prompt sytuacyjny → TTS | **Must** | Asystent autonomicznie komentuje sytuacje w grze |
| F-OB-04 | Konfigurowalny interwał analizy ekranu (np. co 5s, 10s, 30s) | **Should** | Użytkownik wybiera częstotliwość w UI |
| F-OB-05 | Uruchamianie/zatrzymywanie trybu obserwatora komendą głosową lub klawiszem | **Must** | Komenda „Zacznij obserwować" / „Przestań" działa poprawnie |
| F-OB-06 | Detekcja znaczących zmian na ekranie (unikanie analizy statycznych scen) | **Could** | Analiza uruchamiana tylko przy wykryciu istotnej zmiany |

### 2.5 Konfiguracja i UI

| ID | Wymaganie | Priorytet | Akceptacja |
|----|-----------|-----------|------------|
| F-UI-01 | Panel konfiguracji ukrywalny po kliknięciu / skrótem klawiaturowym | **Must** | Panel pojawia się i chowa bez przeszkadzania w grze |
| F-UI-02 | Konfiguracja wyboru monitora (multi-monitor) | **Should** | Awatar wyświetlany na wybranym monitorze |
| F-UI-03 | Ustawienia audio: wybór mikrofonu, głośność TTS | **Should** | Konfiguracja urządzeń audio |
| F-UI-04 | Wybór modelu VRM (awatara) | **Should** | Zmiana awatara z poziomu UI |
| F-UI-05 | System tray icon z szybkim menu | **Could** | Ikona w zasobniku z opcjami: pokaż/ukryj, zamknij |

---

## 3. Wymagania Niefunkcjonalne

### 3.1 Wydajność

| ID | Wymaganie | Wartość docelowa |
|----|-----------|-----------------|
| NF-P-01 | Opóźnienie end-to-end (mowa → odpowiedź audio) | < 3 sekundy |
| NF-P-02 | Wpływ na FPS w grach (tryb obserwatora aktywny) | < 5% spadek |
| NF-P-03 | Zużycie VRAM przez moduły asystenta (bez LLM w LM Studio) | < 4 GB |
| NF-P-04 | Zużycie RAM | < 2 GB |
| NF-P-05 | Czas uruchomienia aplikacji | < 15 sekund |

### 3.2 Bezpieczeństwo i Prywatność

| ID | Wymaganie |
|----|-----------|
| NF-S-01 | Wszystkie dane przetwarzane lokalnie — zero transmisji do chmury |
| NF-S-02 | Brak persystencji nagrań audio (dane usuwane po transkrypcji) |
| NF-S-03 | Zrzuty ekranu usuwane z pamięci po analizie |

### 3.3 Kompatybilność

| ID | Wymaganie |
|----|-----------|
| NF-C-01 | System operacyjny: Windows 10/11 (x64) |
| NF-C-02 | GPU: NVIDIA RTX 30xx+ (z obsługą CUDA) |
| NF-C-03 | Wymagany LM Studio zainstalowany i uruchomiony z załadowanym modelem |

### 3.4 Jakość Kodu i Utrzymanie

| ID | Wymaganie |
|----|-----------|
| NF-Q-01 | Architektura modułowa — każdy komponent (STT, TTS, VLM, LLM) wymienialny |
| NF-Q-02 | API backendu udokumentowane (auto-docs FastAPI / Swagger) |
| NF-Q-03 | Testy jednostkowe dla krytycznych modułów |

---

## 4. Architektura Wysokopoziomowa

```
┌──────────────────────────────────────────────────────────┐
│                    FRONTEND (Electron + React)            │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │  Awatar 3D  │  │  Panel UI /  │  │  Audio Player   │ │
│  │  (Three.js  │  │  Konfiguracja│  │  + Lip-sync     │ │
│  │  + three-vrm│  │              │  │                 │ │
│  └──────┬──────┘  └──────┬───────┘  └────────┬────────┘ │
│         └────────────────┼───────────────────┘          │
│                    WebSocket / HTTP                       │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────┴───────────────────────────────┐
│                   BACKEND (Python + FastAPI)              │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐ │
│  │  Moduł STT │  │  Moduł TTS │  │  Orkiestrator AI   │ │
│  │  (Faster-  │  │  (Piper /  │  │  (Historia, Prompt │ │
│  │  Whisper)  │  │  XTTSv2)   │  │   Management)      │ │
│  └────────────┘  └────────────┘  └─────────┬──────────┘ │
│  ┌────────────┐  ┌────────────┐            │            │
│  │  Moduł     │  │  Screen    │            │            │
│  │  Wakeword  │  │  Capture   │            │            │
│  │(openWake-  │  │  (DXcam)   │            │            │
│  │  word)     │  │            │            │            │
│  └────────────┘  └────────────┘            │            │
│  ┌────────────┐                            │            │
│  │  Moduł VLM │◄───────────────────────────┘            │
│  │ (Moondream │                                         │
│  │  / LLaVA)  │                                         │
│  └────────────┘                                         │
└──────────────────────────┬───────────────────────────────┘
                           │ OpenAI-compatible API
┌──────────────────────────┴───────────────────────────────┐
│                   LM STUDIO (Serwer LLM)                 │
│                   Gemma 4 E4B                            │
└──────────────────────────────────────────────────────────┘
```

---

## 5. Tech Stack

| Warstwa | Technologia | Uzasadnienie |
|---------|-------------|-------------|
| **Frontend** | Electron.js + React.js | Natywne okno z transparentnością i Always-on-Top |
| **Rendering 3D** | Three.js + three-vrm | Dojrzałe rozwiązanie do renderowania modeli VRM w przeglądarce |
| **Backend** | Python 3.10+ / FastAPI | Szybki async framework z auto-dokumentacją; bogaty ekosystem ML |
| **LLM** | Gemma 4 E4B (via LM Studio) | Potężny lokalny model, kompatybilny z OpenAI API |
| **STT** | Faster-Whisper | Zoptymalizowana wersja Whisper z CTranslate2 — szybka i dokładna |
| **Wakeword** | openWakeWord | Lekki, konfigurowalny detektor słów wybudzających |
| **TTS** | Piper / XTTSv2 | Piper: ultraszybki; XTTSv2: klonowanie głosu — do wyboru |
| **VLM** | Moondream2 / LLaVA | Małe modele wizyjne zdolne do analizy zrzutów ekranu |
| **Screen Capture** | DXcam | Najszybsza metoda przechwytywania ekranu na Windows (DirectX) |
| **Input Handling** | pynput | Globalna obsługa klawiszy/myszy (PTT) |

---

## 6. User Stories

### US-01: Rozmowa głosowa z asystentem
> Jako gracz, chcę porozmawiać z asystentem głosowo (PTT lub wakeword), aby uzyskać szybką odpowiedź bez odrywania rąk od klawiatury/myszy.

**Scenariusz (PTT):**
1. Użytkownik przytrzymuje skonfigurowany klawisz (np. `Caps Lock`).
2. System rozpoczyna nagrywanie audio z mikrofonu.
3. Użytkownik zadaje pytanie i zwalnia klawisz.
4. Audio jest transkrybowane (STT → Faster-Whisper).
5. Tekst jest wysyłany do LLM (Gemma 4 E4B via LM Studio).
6. Odpowiedź LLM jest przetwarzana przez TTS.
7. Audio odpowiedzi jest odtwarzane, awatar synchronizuje usta.

### US-02: Automatyczny komentarz do gry
> Jako gracz, chcę włączyć tryb obserwatora, aby asystent automatycznie komentował to, co dzieje się na ekranie.

**Scenariusz:**
1. Użytkownik mówi „Zacznij obserwować" lub naciska klawisz.
2. System aktywuje pętlę obserwatora.
3. Co N sekund: DXcam przechwytuje ekran → VLM analizuje obraz → Gemma generuje komentarz → TTS odczytuje komentarz.
4. Użytkownik mówi „Przestań obserwować" → pętla się zatrzymuje.

### US-03: Konfiguracja awatara
> Jako użytkownik, chcę zmienić wygląd awatara, jego rozmiar i pozycję na ekranie.

**Scenariusz:**
1. Użytkownik otwiera panel konfiguracji (skrót klawiszowy).
2. Wybiera nowy model VRM z dysku.
3. Reguluje rozmiar i przezroczystość suwakami.
4. Przeciąga awatar na żądaną pozycję.
5. Zamyka panel — ustawienia zapisują się automatycznie.

---

## 7. Ryzyka i Ograniczenia

| # | Ryzyko | Prawdopodobieństwo | Wpływ | Mitigacja |
|---|--------|-------------------|-------|-----------|
| R1 | Wysoki VRAM — VLM + LLM + TTS mogą przekroczyć limity GPU | Średnie | Wysoki | Sekwencyjne ładowanie modeli; modele kwantyzowane; profilowanie VRAM |
| R2 | Opóźnienia end-to-end > 3s przy złożonych promptach | Średnie | Średni | Streaming odpowiedzi; cache promptów; optymalizacja pipeline |
| R3 | DXcam niekompatybilny z niektórymi grami (anty-cheat, ekskluzywny fullscreen) | Średnie | Średni | Fallback na inne metody capture; dokumentacja obsługiwanych trybów |
| R4 | Jakość STT dla języka polskiego w hałaśliwym środowisku | Niskie | Średni | Noise suppression preprocessing; wybór modelu Whisper odpowiedni dla PL |
| R5 | Konflikty globalnych skrótów klawiszowych z grami | Niskie | Niski | Konfigurowalność klawiszy; obsługa kolizji |

---

## 8. Fazy Realizacji (MVP → Full)

### Faza 1 — Backend Core (MVP-1)
**Cel:** Działający pipeline głosowy: PTT → STT → LLM → TTS → odtwarzanie audio.

- [ ] Inicjalizacja projektu Python + FastAPI
- [ ] Klient OpenAI API → LM Studio (Gemma 4 E4B)
- [ ] Moduł STT (Faster-Whisper) z nagrywaniem audio
- [ ] Moduł TTS (Piper)
- [ ] Zarządzanie trybami: PTT (pynput) + Wakeword (openWakeWord)
- [ ] REST/WebSocket API dla frontendu

**Kamień milowy:** Użytkownik może rozmawiać z asystentem głosowo z terminala.

---

### Faza 2 — Wizja i Tryb Obserwatora (MVP-2)
**Cel:** Asystent „widzi" ekran i komentuje rozgrywkę.

- [ ] Integracja DXcam z benchmarkiem wydajności
- [ ] Integracja VLM (Moondream2)
- [ ] Pętla obserwatora z konfigurowalnym interwałem
- [ ] Komendy start/stop trybu obserwatora
- [ ] Detekcja zmian sceny (opcjonalnie)

**Kamień milowy:** Asystent automatycznie komentuje rozgrywkę w wybranej grze.

---

### Faza 3 — Frontend i Awatar 3D (Release)
**Cel:** Pełna aplikacja desktopowa z awatarem 3D.

- [ ] Electron + React setup (frameless, transparent, Always-on-Top)
- [ ] Renderer Three.js + three-vrm
- [ ] Lip-sync na podstawie strumienia audio (WebSocket)
- [ ] Panel konfiguracji (mikrofon, awatar VRM, tryby)
- [ ] Animacje idle
- [ ] System tray icon

**Kamień milowy:** Kompletna aplikacja gotowa do codziennego użytku.

---

## 9. Pytania Otwarte (do sesji planistycznej)

> [!IMPORTANT]
> Poniższe pytania wymagają decyzji przed rozpoczęciem implementacji.

1. **TTS: Piper vs XTTSv2** — Piper jest szybszy, ale XTTSv2 oferuje klonowanie głosu. Który model wybrać jako domyślny? Czy wspierać oba z przełączaniem?
2. **VLM: Moondream2 vs LLaVA** — Moondream2 jest lżejszy (~1.5 GB VRAM), LLaVA bardziej zdolna. Czy priorytetem jest wydajność czy jakość analizy?
3. **Język interfejsu** — Czy asystent ma działać w trybie dwujęzycznym (PL/EN), czy priorytetowo w jednym języku?
4. **Persystencja ustawień** — Gdzie przechowywać konfigurację? JSON w `%APPDATA%`? SQLite?
5. **Multi-monitor** — Który monitor przechwytywać w trybie obserwatora? Czy użytkownik wskazuje monitor, czy auto-detekcja aktywnego okna gry?
6. **Fullscreen vs Borderless** — Awatar jako overlay działa w borderless. Czy wspieramy ekskluzywny fullscreen (wymaga innego podejścia)?
7. **Model zarządzania VRAM** — Czy VLM powinien być ładowany stale, czy dynamicznie (ładuj-analizuj-zwolnij) aby oszczędzać VRAM?
8. **System aktualizacji** — Czy przewidujemy auto-update (electron-updater) czy ręczne aktualizacje?

---

## 10. Definition of Done (DoD) — MVP

- [ ] Użytkownik może rozmawiać z asystentem głosowo (PTT + Wakeword)
- [ ] Asystent odpowiada płynnym głosem (TTS)
- [ ] Awatar 3D wyświetla się jako nakładka na ekranie
- [ ] Usta awatara synchronizują się z mową
- [ ] Tryb obserwatora analizuje ekran i komentuje rozgrywkę
- [ ] Panel konfiguracji umożliwia zmianę podstawowych ustawień
- [ ] Całość działa offline, bez transmisji danych do chmury
- [ ] Wpływ na FPS w grach < 5%

---

*Dokument przygotowany na sesję planistyczną. Wymaga przeglądu i zatwierdzenia przed rozpoczęciem implementacji.*
