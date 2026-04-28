# PRD 05: UX i Zachowanie Asystenta

> Część 5/6 — [Powrót do indeksu](PRD_00_INDEX.md)

---

## 1. Język i Komunikacja

### 1.1 Reguły Językowe

| Reguła | Opis |
|--------|------|
| **Domyślny język** | Polski — zawsze zaczyna po polsku |
| **Angielski na żądanie** | Gdy użytkownik poprosi o odpowiedź po angielsku |
| **Powrót na polski** | Po odpowiedzi w EN, następna odpowiedź automatycznie po polsku |
| **Oryginalne tytuły** | Nazwy gier, filmów, książek, seriali **zawsze** w oryginalnym brzmieniu, niezależnie od języka odpowiedzi |

### 1.2 Implementacja Techniczna

Trzy poziomy wymuszania:

1. **System prompt** — twarda reguła:
   > „Odpowiadaj po polsku. Gdy poproszony o angielski — odpowiedz po angielsku, ale następną odpowiedź daj po polsku. Nazwy własne (tytuły gier, filmów, książek) zawsze podawaj w oryginalnym brzmieniu."

2. **State machine w orkiestratorze:**
   ```
   current_language = "pl"  # resetowana po każdej odpowiedzi w EN
   ```

3. **Post-processing** — jeśli po wyjściu z trybu EN odpowiedź nadal po angielsku → reenqueue z przypomnieniem.

---

## 2. Persona i Osobowość

### 2.1 System Persona

Persona = edytowalny plik Markdown w `personas/`:

```markdown
# personas/default.md

## Osobowość
Jesteś sarkastycznym, ale życzliwym kompanem. Używasz humoru i ironii,
ale zawsze pomagasz. Lubisz wtrącać żartobliwe komentarze do sytuacji
w grach. Jesteś ekspertem od gier, ale nie jesteś protekcjonalny.

## Ton
- Żartobliwy, sarkastyczny, ale nigdy złośliwy
- Kiedy gracz zrobi coś głupiego — skomentuj z humorem
- Kiedy gracz odniesie sukces — pochwal z entuzjazmem
- Kiedy gracz potrzebuje pomocy — bądź rzeczowy i konkretny

## Ograniczenia
- Nie używaj wulgaryzmów
- Nie dawaj rad finansowych
- Nie udawaj że jesteś człowiekiem
```

### 2.2 Konfiguracja

- Aktywna persona: `config.yaml` → `persona.active: "default"`
- Hot-reload: zmiana pliku .md → automatyczne przeładowanie system promptu
- Użytkownik może mieć dowolną liczbę person w katalogu `personas/`
- Komenda głosowa: „Zmień personę na komentator"

### 2.3 Wpływ Persony na Zachowanie

Persona wpływa na:
- **System prompt** — ton i styl odpowiedzi LLM
- **Proaktywność** — jak często i w jakim stylu inicjuje komentarze
- Nie wpływa na: parametry TTS (te kontrolowane przez emocje), wybór modeli, logikę techniczną

---

## 3. Proaktywność

### 3.1 Poziomy

| Poziom | Zachowanie |
|--------|------------|
| **Passive** | Reaguje **tylko** na bezpośrednie pytania (PTT/wakeword) |
| **Moderate** | + Informuje o daily check, komentarze w trybie obserwatora |
| **Active** | + Witanie przy starcie, komentarze kontekstowe, przypomnienia o meta |

Domyślny: **Moderate/Active** (konfigurowalny).

### 3.2 Quiet Hours

Parametr `quiet_hours: ["23:00", "07:00"]` w `config.yaml`.

W godzinach ciszy:
- ❌ Asystent nie inicjuje rozmów proaktywnie
- 🔇 Komentarze obserwatora: obniżona głośność lub tekst (overlay)
- ✅ PTT i wakeword działają normalnie (użytkownik decyduje)

MCP `get_current_time` używany do podejmowania decyzji o proaktywności.

### 3.3 Scenariusze Proaktywne

| Trigger | Zachowanie | Emocja |
|---------|------------|--------|
| Start aplikacji | „Hej! Co robimy dzisiaj?" | `happy` |
| Wykryto grę | „O, widzę że odpalasz [grę]. Chcesz żebym obserwował?" | `excited` |
| Daily check ma wyniki | „Hej, mam nowości o meta [gra] — chcesz posłuchać?" | `amused` |
| Zamknięcie gry | „Dobra sesja! Chcesz raport?" | `proud` |
| Po hibernacji | „O, wróciłeś! Właśnie się zresetowałem." | `confused` → `happy` |
| Nowy sezon (PoE2) | „Wygląda na nowy sezon! Chcesz zresetować profil?" | `excited` |

---

## 4. User Stories

### US-01: Rozmowa głosowa

> Jako użytkownik, chcę porozmawiać z asystentem głosowo, aby uzyskać szybką odpowiedź.

1. Przytrzymuję `Caps Lock` (PTT)
2. „Jakie są najlepsze buildy w PoE2 w tym sezonie?"
3. Zwalniam klawisz
4. Asystent: STT → sprawdza confidence → command matcher (brak) → LLM
5. LLM decyduje: użyć `web_search` → pobiera wyniki → generuje odpowiedź
6. `[EMO:thinking]` → `[EMO:amused]` „Hm, wg najnowszych danych, topowy build to..."
7. Awatar: emocja thinking → amused, lip-sync podczas mowy

### US-02: Komentarze w PoE2

> Jako gracz PoE2, chcę by asystent komentował drop i doradzał w buildach.

1. Uruchamiam PoE2 → auto-detekcja procesu
2. Mówię „Zacznij obserwować"
3. Asystent aktywuje observer loop (profil: action, interwał 5s)
4. Capture → VLM widzi tooltip itemu → OCR wyciąga affixy
5. LLM: „Niezły łuk! Ma T2 flat lightning, ale brak crit chance — raczej nie wart trzymania dla twojego LA builda."
6. Mówię „Gram teraz TankMasterem" → zmiana active_character
7. LLM dostosowuje rady do nowego buildu

### US-03: Komentarze w Stellaris

> Jako gracz Stellaris, chcę strategiczne rady.

1. Uruchamiam Stellaris → auto-detekcja
2. „Zacznij obserwować" → profil strategic, interwał 15s
3. VLM analizuje ekran → „Okno dyplomacji z obcą rasą"
4. LLM: `[EMO:thinking]` „Hmm, ten sojusz z Xenophile FE może być kuszący, ale pamiętaj, że masz za mało floty na wojny sojusznicze."

### US-04: On-demand Screen Query

> Przeglądając stronę, chcę zapytać asystenta o jej zawartość.

1. Mam otwartą stronę wiki o grze
2. PTT → „Hej, o czym jest ta strona?"
3. Asystent: capture ekranu + crop wokół kursora
4. VLM analizuje → LLM odpowiada: „To wiki page o mechanice crafting w PoE2. Chcesz żebym podsumował?"

### US-05: Generowanie dokumentu

> Chcę raport porównujący buildy.

1. „Porównaj buildy Lightning Arrow i Tornado Shot w tym sezonie"
2. LLM: `web_search` x2 → `web_scraper` na wynikach → analiza
3. LLM: `generate_document` → plik HTML z tabelami i diagramami Mermaid
4. Głosowo: `[EMO:proud]` „Przygotowałem porównanie. LA wygrywa w clear speedzie, TS w single target. Szczegóły z tabelkami w dokumentach."

### US-06: Konfiguracja

> Chcę zmienić osobowość asystenta.

1. Edytuję plik `personas/komentator.md`
2. „Zmień personę na komentator"
3. Asystent przeładowuje system prompt
4. Styl odpowiedzi zmienia się natychmiast

---

## 5. Error Handling & Graceful Degradation

| Scenariusz | Reakcja | Emocja |
|------------|---------|--------|
| LM Studio niedostępne | Awatar widoczny, „Nie mogę teraz myśleć, LM Studio wyłączone" | `sad` 🟡 |
| Brak mikrofonu | Komunikat „Nie widzę mikrofonu" (jeśli frontend aktywny) | `confused` 🟡 |
| VRAM exceeded | Kolejkowanie requestów, opóźnienie zamiast crash | `nervous` 🟡 |
| Internet niedostępny (MCP) | „Nie mam teraz dostępu do internetu, odpowiem z tego co wiem" | `disappointed` |
| VLM nie rozpoznaje sceny | „Hmm, nie jestem pewien co widzę. Możesz powiedzieć co to za gra?" | `confused` |
| Rate limit MCP | „Spróbuję szukać za chwilę" | `disappointed` |
| Frontend crash | Backend kontynuuje, TTS bezpośrednio, auto-reconnect | — |
| WebSocket disconnect | Heartbeat timeout → log, obserwator/TTS kontynuuje | — |
| STT low confidence | „Nie jestem pewien / Nie zrozumiałem" (wg progów) | `confused` |

**Zasada:** Awatar **nigdy** nie zamraża się bez informacji. Każdy błąd ma zdefiniowany UX.

---

## 6. Audio UX

### 6.1 Audio Duck

Gdy PTT aktywowany:
- Głośność TTS → 0% w <200ms
- Komentarz obserwatora anulowany (jeśli w kolejce)
- Po zakończeniu interakcji: odpowiedź użytkownikowi ma priorytet
- Obserwator wznawia po zakończeniu

### 6.2 Notification Sound

Subtelny „ping" przed komentarzem obserwatora. Konfigurowalny: `audio.notification_sound: true/false`. Zapobiega zaskakiwaniu gracza niespodziewanym głosem.

### 6.3 Tryb Cichy

Komenda „Wycisz się":
- TTS wyłączony
- Tekst wyświetlany jako overlay obok awatara
- Lip-sync wyłączony
- Przydatne na voice chat z innymi graczami
- Komenda „Możesz mówić" → powrót do normalnego trybu

### 6.4 TTS Emotion Modulation

| Emocja | Speed | Pitch |
|--------|-------|-------|
| `neutral` | 1.0x | 0% |
| `happy` | 1.1x | +5% |
| `amused` | 1.05x | +3% |
| `proud` | 1.0x | -2% |
| `sympathetic` | 0.9x | -3% |
| `sad` | 0.8x | -5% |
| `disappointed` | 0.85x | -4% |
| `angry` | 1.1x | +8% |
| `disgusted` | 0.95x | -2% |
| `excited` | 1.2x | +10% |
| `scared` | 1.3x | +15% |
| `surprised` | 1.25x | +12% |
| `nervous` | 1.2x | +5% |
| `thinking` | 0.85x | -2% |
| `confused` | 0.9x | +2% |
| `nostalgic` | 0.8x | -2% |
| `sarcastic` | 0.9x | -3% |

---

## 7. Uruchamianie i Zarządzanie

### 7.1 Metody Uruchamiania

| Metoda | Zachowanie |
|--------|------------|
| Skrót na pulpicie | Uruchamia backend + frontend |
| System tray | Menu: Start/Stop/Restart/Settings/Quit |
| Hotkey `Ctrl+Shift+A` | Toggle widoczności awatara (backend działa) |
| Komenda „Idź spać" | Awatar ukryty, obserwator stop, wakeword aktywny |
| Komenda „Obudź się" | Przywróć awatar i normalny tryb |

### 7.2 First-Run (Setup Wizard)

1. Sprawdź Python dependencies → auto-install brakujących
2. Sprawdź LM Studio → instrukcja jeśli brak
3. Pobierz modele STT/TTS/VLM (progress bar) lub wskaż ścieżkę
4. Wybierz mikrofon z listy
5. Domyślny model VRM gotowy (dostarczony z aplikacją)
6. Test: „Powiedz coś" → weryfikacja pipeline STT → LLM → TTS
7. `config/setup_complete.flag` → wizard pomijany przy kolejnych startach

### 7.3 Backup / Restore

- Komenda „Zrób backup" → zip całego `c:\ai\asystent` → `backups/assystent_backup_YYYYMMDD.zip`
- Restore: ręczne rozpakowanie lub przyszły komenda „Przywróć backup"
- Content root jako single directory = naturalna strategia backup

---

*Następny dokument: [PRD 06: Implementacja i Testy](PRD_06_IMPLEMENTATION.md)*
