# DOK-15: RISK_REGISTER.md — Rejestr Ryzyk

> **Status:** v1.0 — 2026-05-02
> **Materiały źródłowe:** PRD_06_IMPLEMENTATION.md §4, wszystkie DOK-01–DOK-12

---

## Risk Matrix (Probability × Impact)

```
Impact →    1-Niski    2-Średni    3-Wysoki    4-Krytyczny
Prob ↓
4-Pewne                            R05         
3-Wysokie              R04,R09     R01,R02     
2-Średnie   R15,R20    R07,R10     R03,R06     R08
1-Niskie    R18,R19    R14,R16     R11,R12     R13,R17
```

---

## Top 5 Ryzyk (pełne playbooki)

### R01: VRAM Exhaustion podczas gry — Score: 12

| Pole | Wartość |
|------|---------|
| Kategoria | Performance / Resource |
| Probability | 3/4 — Wysokie |
| Impact | 4/4 — Krytyczny |
| Owner | Solo-dev |

**Opis:** RTX 5090 (32GB). Gra (8-12GB) + LLM w LM Studio (5-6GB) + VLM (2GB) + STT (1.5GB) + OCR (0.5GB) ≈ 17-22GB. Peak z teksturami lategame → risk OOM.

**Symptomy:** `nvidia-smi` VRAM > 28GB, CUDA OOM w log, user: "asystent zwolnił"

**Mitygacje:**
1. GPU Scheduler — sequential inference, nigdy 2 modele jednocześnie
2. Lekkie domyślne modele (Piper CPU, Whisper int8, Moondream2 int8)
3. VRAM monitor co 30s → warning przy >90%
4. `models.vlm_enabled: false` jako instant relief

**Playbook:**
1. Detect OOM → emotion `nervous`, TTS "Mam problem z pamięcią karty"
2. Auto: VLM unload, observer pause
3. TTS "Wyłączyłem obserwator żeby zwolnić pamięć"
4. Po 60s → retry VLM reload jeśli VRAM < 20GB

**KPI:** 0 CUDA OOM w 10h gameplay, VRAM peak < 30GB p95

---

### R02: LLM Hallucinations — Score: 12

| Pole | Wartość |
|------|---------|
| Kategoria | UX / Data Quality |
| Probability | 3/4 |
| Impact | 4/4 |

**Opis:** Fałszywe info o buildach, item stats, mechanikach → user podejmuje złe decyzje w grze.

**Mitygacje:**
1. Zero-hallucination rule w base prompt (DOK-05)
2. "Nie wiem" jako poprawna odpowiedź
3. web_search verification dla game meta
4. Persona: "Nigdy nie zmyślaj faktów"

**KPI:** < 2% hallucinations w 100 test queries

---

### R03: DXcam Blocked by Anti-Cheat/AV — Score: 6

| Pole | Wartość |
|------|---------|
| Kategoria | Compatibility |
| Probability | 2/4 |
| Impact | 3/4 |

**Mitygacje:**
1. `pyautogui` fallback (`config.observer.capture_backend: pyautogui`)
2. AV whitelist instructions w ENV_SETUP §9.5
3. User notification via TTS

---

### R04: STT Accuracy for Polish Gaming Jargon — Score: 6

| Pole | Wartość |
|------|---------|
| Kategoria | UX |
| Probability | 3/4 |
| Impact | 2/4 |

**Mitygacje:**
1. Fuzzy command matching (Levenshtein ≤ 2)
2. Diacritics normalization (ą→a, ś→s)
3. Dual threshold: high confidence → execute, low → LLM fallback
4. Wakeword fallback "Hey Jarvis" (pretrained, reliable)

---

### R05: Solo-Dev Scope Creep — Score: 12

| Pole | Wartość |
|------|---------|
| Kategoria | Project |
| Probability | 4/4 |
| Impact | 3/4 |

**Mitygacje:**
1. MoSCoW priority — cut Could/Should first
2. Weekly milestone gates z DEFINITION_OF_DONE
3. 20% buffer per tydzień (piątek PM)
4. "Good enough" > "perfect" mindset

**Cut list (jeśli slipping):**
- Phase 1: Wyrzuć wakeword (PTT only), ogranicz komendy do 8 core
- Phase 2: Wyrzuć daily meta check, season reset, ambient observer
- Phase 3: Wyrzuć setup wizard, config panel (CLI config only), ogranicz do 8 emocji

---

## Pozostałe ryzyka (skrócone)

| ID | Ryzyko | P×I | Mitygacja |
|----|--------|-----|-----------|
| R06 | LM Studio API breaking change | 6 | Pin version, adapter pattern |
| R07 | ChromaDB index corruption | 4 | Regenerate from SQLite messages |
| R08 | SQLite corruption (power loss) | 8 | WAL mode, periodic VACUUM |
| R09 | Model deprecation (Moondream/Whisper) | 6 | Strategy pattern, swap w config |
| R10 | Complexity creep (overengineering) | 4 | YAGNI, simple first |
| R11 | Windows update breaks DXcam | 3 | pyautogui fallback |
| R12 | Game exclusive fullscreen blocks capture | 3 | Borderless windowed recommendation |
| R13 | Data leak via web_search queries | 4 | Query sanitization, no PII |
| R14 | False positive commands | 2 | Confidence threshold 0.75 |
| R15 | Piper TTS quality insufficient | 2 | XTTSv2 upgrade path in config |
| R16 | openWakeWord no Polish models | 2 | "Hey Jarvis" fallback, custom training |
| R17 | EasyOCR fails on stylized game fonts | 4 | OCR optional (VLM-only mode) |
| R18 | DuckDuckGo rate limits/blocks | 1 | SearXNG fallback in config |
| R19 | Playwright Chromium download fails | 1 | httpx-only mode, skip SPA sites |
| R20 | Config migration breaks user settings | 2 | Backup before migrate, `extra="ignore"` |

---

## Risk Review Schedule

| Kiedy | Akcja |
|-------|-------|
| Po Fazie 1 | Re-evaluate R01, R04, R05. Update P×I. |
| Po Fazie 2 | Re-evaluate R03, R06, R17. Add new risks. |
| Po Fazie 3 | Final audit. Close resolved. |
| Przy zmianie scope | Immediate review of R05, R10. |

---

*Dokument: DOK-15 RISK_REGISTER.md v1.0 — 2026-05-02*
