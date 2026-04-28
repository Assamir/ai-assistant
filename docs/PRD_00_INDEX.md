# PRD: Lokalny Asystent AI — Indeks Dokumentów

> **Status:** v1.0 — Finalna wersja po sesji planistycznej  
> **Data:** 2026-04-25  
> **Projekt:** Assystent  
> **Typ:** Użytek osobisty (solo-dev)

---

## Struktura PRD

PRD został podzielony na 6 dokumentów tematycznych:

| # | Dokument | Opis |
|---|----------|------|
| 01 | [Wizja i Cele](PRD_01_VISION.md) | Problem, grupa docelowa, cele produktu, metryki sukcesu |
| 02 | [Wymagania Funkcjonalne](PRD_02_FUNCTIONAL.md) | Awatar, głos, AI, obserwator, MCP tools, dokumenty, UI |
| 03 | [Wymagania Niefunkcjonalne](PRD_03_NONFUNCTIONAL.md) | Wydajność, bezpieczeństwo, kompatybilność, jakość kodu |
| 04 | [Architektura i Tech Stack](PRD_04_ARCHITECTURE.md) | Architektura, tech stack, struktura katalogów, przepływy danych |
| 05 | [UX i Zachowanie](PRD_05_UX_BEHAVIOR.md) | Emocje, persony, język, proaktywność, komendy, error handling |
| 06 | [Implementacja i Testy](PRD_06_IMPLEMENTATION.md) | Fazy realizacji, strategia testowania, ryzyka, DoD |

---

## Kluczowe Decyzje Projektowe

Decyzje podjęte w sesji planistycznej (8 rund pytań, 60+ decyzji):

- **Tryb:** Offline-first z opcjonalnym internetem (MCP)
- **Content root:** `c:\ai\asystent` (oddzielnie od kodu źródłowego)
- **Język:** Polski domyślny, angielski na żądanie, oryginalne tytuły zawsze
- **Persona:** Żartobliwie sarkastyczny, w pełni konfigurowalny via pliki .md
- **Emocje:** 16 stanów z proceduralnymi animacjami
- **Obserwator:** Game loop + on-demand (pozycja kursora)
- **Pamięć:** SQLite + ChromaDB, konfigurowalny backend (→ Postgres/GCP)
- **Sandbox:** Twardy — brak dostępu do schowka, OS, dysku poza content root
- **MCP Tools:** 6 narzędzi (web_search, web_scraper, get_time, calculator, generate_document, screen_capture)
- **Testy:** pytest z mockami, minimalne testy integracyjne z LLM

---

*Każdy dokument jest samodzielny, ale wzajemnie się uzupełniają. Czytaj w kolejności numerycznej.*
