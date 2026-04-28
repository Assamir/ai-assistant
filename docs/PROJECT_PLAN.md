# Wstępny Plan Projektu: Lokalny Asystent Gracza

## Cel Projektu
Stworzenie lokalnego asystenta głosowego z trójwymiarowym, konfigurowalnym awatarem (nakładką na ekran), wspieranego przez model Gemma 4 E4B (uruchomiony w LM Studio). Asystent ma wspierać użytkownika podczas korzystania z komputera oraz automatycznie komentować rozgrywkę w grach, wykorzystując zmysł "wzroku" (analizę zrzutów ekranu).

## 1. Kluczowe Wymagania (do rozwinięcia w PRD)
*   **Awatar:** 3D (.vrm), konfigurowalny (skalowalność, przezroczystość, Always-on-Top), renderowany na wybranym monitorze lub nakładany na grę.
*   **Komunikacja Głosowa:** Dwa przełączalne tryby:
    *   Push-to-Talk (PTT) pod przypisanym klawiszem/przyciskiem myszy.
    *   Ciągłe nasłuchiwanie słowa wybudzającego (Wakeword np. "Hej Asystent").
*   **Automatyzacja (Komentowanie):** Tryb obserwatora uruchamiany i zatrzymywany wybraną komendą. Asystent w tle analizuje ekran i sam inicjuje rozmowę/komentarz do sytuacji w grze.
*   **Architektura LLM:** Wykorzystanie lokalnego modelu Gemma 4 E4B z serwera LM Studio (kompatybilność z OpenAI API).
*   **Wydajność:** Narzędzia dobrane pod kątem zminimalizowania użycia procesora, VRAM i opóźnień (dzięki wykorzystaniu zasobów RTX 5090).

## 2. Wstępny Tech Stack (do rozwinięcia w Tech Stack Doc)
*   **Frontend (UI/Awatar):** Electron.js + React.js + Three.js (biblioteka three-vrm).
*   **Backend (Core Logiki):** Python 3.10+ z frameworkiem FastAPI.
*   **AI/ML:**
    *   LLM: Gemma 4 E4B (via LM Studio).
    *   STT (Speech-to-Text): Faster-Whisper.
    *   Wakeword: openWakeword.
    *   TTS (Text-to-Speech): Piper lub XTTSv2.
    *   Wizja/VLM: Moondream2 / LLaVA (lub podobny mały model wizyjny do opisywania obrazu).
*   **Narzędzia systemowe:**
    *   Zrzuty ekranu: DXcam (najszybsza metoda na Windows).
    *   Obsługa klawiatury/myszy (PTT): pynput.

## 3. Fazy Implementacji (struktura pod Cursor)

### Faza 1: Backend & Komunikacja (Python)
Cel: Budowa rdzenia systemu obsługującego przetwarzanie języka naturalnego i audio.
1.  Inicjalizacja środowiska Python i FastAPI.
2.  Połączenie z API LM Studio (Gemma 4 E4B).
3.  Moduł STT (nagrywanie dźwięku + Whisper).
4.  Moduł zarządzania trybami nagrywania (PTT z pynput oraz Wakeword).
5.  Moduł TTS (generowanie audio z tekstu).

### Faza 2: Wizja & Tryb Obserwatora (Python)
Cel: Nadanie asystentowi zmysłu wzroku i logiki autonomicznej.
1.  Integracja DXcam do błyskawicznego przechwytywania ekranu z zachowaniem wysokiej ilości FPS w grach.
2.  Podłączenie lokalnego modelu VLM do interpretacji zrzutów ekranu.
3.  Pętla "Obserwatora" sterująca przepływem: Zrzut -> Analiza VLM -> Prompt sytuacyjny do Gemmy -> Odpowiedź głosowa (TTS).

### Faza 3: Frontend & Awatar 3D (Electron + React)
Cel: Budowa interfejsu użytkownika i wizualizacji asystenta.
1.  Setup środowiska Electron z konfiguracją okna (transparentność, frameless, Always-on-Top).
2.  Integracja środowiska 3D (Three.js) i ładowanie wybranego modelu `.vrm`.
3.  Implementacja animacji ust (lip-sync) na podstawie strumienia audio odbieranego z backendu za pomocą WebSockets.
4.  Stworzenie prostego UI do konfiguracji ukrywanego po kliknięciu (wybór mikrofonu, zmiana modelu VRM, przełączanie PTT/Wakeword).

---
*Dokument roboczy, będzie modyfikowany na podstawie szczegółowych dokumentów PRD i Architektury.*
