# PRD 01: Wizja i Cele Produktu

> Część 1/6 — [Powrót do indeksu](PRD_00_INDEX.md)

---

## 1. Wizja Produktu

Lokalny, w pełni prywatny asystent AI z trójwymiarowym awatarem, który towarzyszy użytkownikowi podczas korzystania z komputera. Asystent komunikuje się głosowo, analizuje obraz na ekranie, autonomicznie komentuje rozgrywkę w grach, wyszukuje informacje w internecie, generuje dokumenty i raporty, oraz pełni rolę ogólnego kompana — odpowiadając na pytania niezależnie od kontekstu (gaming, praca, przeglądanie).

Asystent działa jako **inteligentny kompan** z konfigurowalną osobowością (domyślnie: żartobliwie sarkastyczny), oparty o modele AI uruchamiane lokalnie na GPU użytkownika.

---

## 2. Problem

| # | Problem | Jak rozwiązujemy |
|---|---------|-----------------|
| P1 | Asystenty AI (Copilot, Alexa, Google) wymagają chmury — brak prywatności | 100% przetwarzania lokalnie, zero transmisji danych |
| P2 | Brak asystentów gamingowych z analizą ekranu i komentowaniem | Tryb obserwatora z VLM + autonomiczne komentarze |
| P3 | Brak immersyjnej prezencji (awatar 3D) | Awatar VRM z 16 emocjami, lip-sync, animacjami |
| P4 | Asystenty nie pamiętają kontekstu między sesjami | Lokalna baza danych z pamięcią semantyczną |
| P5 | Brak wsparcia buildów/meta w grach w czasie rzeczywistym | MCP tools + daily meta check + pamięć buildu gracza |

---

## 3. Grupa Docelowa

Produkt do **użytku osobistego** (solo-dev, brak dystrybucji).

**Profil użytkownika:**
- Gracz PC z wydajnym sprzętem (RTX 5090, 32 GB VRAM)
- Najczęściej grane tytuły: Stellaris (strategia), Path of Exile 2 (action-RPG)
- Ceni prywatność i lokalność przetwarzania
- Power user — komfortowy z edycją plików YAML/MD

---

## 4. Cele Produktu i Metryki Sukcesu

| # | Cel | Metryka sukcesu |
|---|-----|-----------------|
| C1 | Offline-first z opcjonalnym internetem | Core funkcjonalność działa bez internetu; MCP tools degradują gracefully |
| C2 | Minimalne obciążenie systemu podczas gry | < 5% spadek FPS (Stellaris lategame, PoE2 mapping) |
| C3 | Naturalna interakcja głosowa | End-to-end latency < 3s (STT < 0.5s, LLM TTFT < 0.5s, LLM full < 1.5s, TTS < 0.5s) |
| C4 | Użyteczne komentarze i rady do rozgrywki | Poprawne rozpoznanie gry, kontekstowe komentarze, wsparcie buildów |
| C5 | Ekspresyjny awatar | 16 emocji z unikalnymi animacjami, lip-sync, stany wizualne systemu |
| C6 | Ogólny kompan (nie tylko gaming) | Odpowiedzi na pytania, wyszukiwanie, generowanie dokumentów niezależnie od kontekstu |

---

## 5. Tryb Działania

### 5.1 Offline-first z opcjonalnym internetem

```
┌─────────────────────────────────────────────────────────┐
│                    TRYBY DZIAŁANIA                       │
├──────────────────────────┬──────────────────────────────┤
│       OFFLINE            │         ONLINE               │
├──────────────────────────┼──────────────────────────────┤
│ ✅ Rozmowa głosowa (STT) │ ✅ Wszystko z OFFLINE        │
│ ✅ Odpowiedzi LLM        │ ✅ MCP Web Search            │
│ ✅ TTS + Lip-sync        │ ✅ MCP Web Scraper           │
│ ✅ Obserwator gier       │ ✅ Daily meta check          │
│ ✅ Emocje awatara        │ ✅ Import buildów z URL      │
│ ✅ Komendy systemowe     │ ✅ Aktualne info z wiki      │
│ ✅ Pamięć lokalna        │                              │
│ ✅ Generowanie dokumentów│                              │
│ ❌ Wyszukiwanie w sieci  │                              │
└──────────────────────────┴──────────────────────────────┘
```

Przy starcie asystent sprawdza dostępność internetu i informuje o trybie. Brak internetu **nigdy** nie blokuje działania.

### 5.2 Stany Operacyjne (Maszyna Stanów)

| Stan | Opis | Obserwator | Interakcja głosowa |
|------|------|------------|-------------------|
| **Idle** | Czeka na interakcję, odpowiada na pytania ogólne | ❌ | ✅ PTT + Wakeword |
| **Observer Active** | Jak Idle + pętla obserwatora w tle | ✅ Game loop | ✅ PTT + Wakeword |
| **Conversation Lock** | Użytkownik aktywnie rozmawia | ⏸️ Wstrzymany | ✅ Aktywna rozmowa |
| **Sleep** | Komenda „Idź spać" — awatar ukryty | ❌ | ✅ Tylko wakeword |

---

## 6. Stany Zdrowia Systemu (Circuit Breaker)

| Stan | Warunek | Zachowanie |
|------|---------|------------|
| **Healthy** 🟢 | Wszystkie komponenty dostępne | Pełna funkcjonalność |
| **Degraded** 🟡 | LM Studio niedostępne | Awatar widoczny (emocja `sad`), PTT/wakeword aktywne, odpowiedź: „Nie mogę teraz myśleć, LM Studio wyłączone". Obserwator zatrzymany |
| **Minimal** 🔴 | Krytyczny błąd (brak GPU, crash) | Tylko awatar + system tray, komunikat „Oczekuję na zasoby…" |

**Circuit breaker:** Po 3 nieudanych połączeniach z LM Studio → stan OPEN (przestaje próbować). Co 30s HALF-OPEN (jeden ping). Sukces → CLOSED.

**SessionWatchdog:** Wątek sprawdzający co 5s stan komponentów. Po hibernacji (skok czasu >30s): reconnect WebSocket, ping LM Studio (retry co 5s), reinicjalizacja mikrofonu. Awatar: `confused` → `happy` z komunikatem „O, wróciłeś!"

---

*Następny dokument: [PRD 02: Wymagania Funkcjonalne](PRD_02_FUNCTIONAL.md)*
