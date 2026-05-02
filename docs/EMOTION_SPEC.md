# DOK-06: EMOTION_SPEC.md — Specyfikacja Emocji i Animacji

> **Status:** v1.0 — 2026-04-30
> **Materiały źródłowe:** PRD_02_FUNCTIONAL.md (§1 Awatar), PRD_05_UX_BEHAVIOR.md (§6.4 TTS Modulation)
> **Docelowi czytelnicy:** Developer frontend (Three.js + three-vrm), developer backend (TTS modulation, orchestrator)
> **Plik runtime:** `emotions.json` (sekcja 11) — machine-readable, ładowany przez frontend przy starcie

---

## Reguły naczelne uwzględnione w tym dokumencie

| # | Reguła | Materializacja |
|---|--------|---------------|
| 6 | Awatar nigdy nie zamarza | Każdy stan systemu i każda emocja mają zdefiniowaną wizualizację; fallback 3-warstwowy |
| 4 | Modularność | Blendshapes / aura / body to niezależne warstwy; można wyłączyć dowolną |

---

## 1. Architektura Systemu Emocji

### 1.1 Trzy niezależne warstwy

```
Emocja (string) ─────────────────────────────────────────
        │
        ├── Layer 1: Blendshapes (VRM expressions)
        │       vrm.expressionManager.setValue("happy", 1.0)
        │       Dostępność: zależna od modelu (skanowanie przy ładowaniu)
        │
        ├── Layer 2: Aura / shader (Three.js PointLight + MeshBasicMaterial)
        │       Zawsze dostępna, niezależna od modelu VRM
        │
        └── Layer 3: Body animation (VRMHumanoid bone rotations)
                Dostępna gdy model ma full humanoid rig
```

Wszystkie warstwy działają jednocześnie. Jeśli Layer 1 niedostępna — Layer 2 i 3 nadal działają.

### 1.2 Dwa niezależne systemy

| System | Sterowanie | Może kumulować się z drugim |
|--------|------------|---------------------------|
| **Emotion System** | LLM `[EMO:tag]` lub `persona.tts_emotion_bias` | Tak |
| **Visual State System** | Orkiestrator (stan pipeline) | Tak |

Przykład kumulacji: `thinking` (Visual State = pulsująca aura niebieska) + `sad` (Emotion = niebieska aura + blendshape) → oba efekty nakładają się (additive blend).

---

## 2. Specyfikacja 16 Emocji

### Konwencje nazw blendshapes (VRM 1.0 / three-vrm)

| Klucz w API | Opis |
|-------------|------|
| `happy` | Uśmiech, zmrużone oczy |
| `sad` | Smutna mina, opuszczone kąciki ust |
| `angry` | Zmarszczone brwi, zaciśnięte usta |
| `surprised` | Szeroko otwarte oczy i usta |
| `relaxed` | Spokojny, półprzymknięte powieki |
| `neutral` | Brak ekspresji |
| `blinkLeft` / `blinkRight` | Mruganie (0.0–1.0) |
| `lookUp` / `lookDown` / `lookLeft` / `lookRight` | Kierunek spojrzenia |
| `aa` / `ih` / `ou` / `ee` / `oh` | Fonemy ust (lip-sync) |

Dostępność weryfikowana przy ładowaniu modelu → `model_capabilities.json` (sekcja 7).

---

### 2.1 `happy`

| Właściwość | Wartość |
|-----------|---------|
| **Triggery** | Sukces gracza, level up, drop rzadkiego itemu, powitanie, daily check pozytywny |
| **Blendshapes** | `happy: 1.0`, `relaxed: 0.3` |
| **Aura color** | `#FFD700` (złoty) |
| **Aura intensity** | 0.7 |
| **Aura pulse** | tak, 1.5 Hz |
| **Head tilt** | 5° prawo (oś Z), oscylacja ±2°, 1.5 Hz |
| **Body sway** | ±3° oś Z, 2.0 Hz |
| **Entry animation** | translateY +0.06 (podskoczenie) → spring-back 400ms |
| **TTS speed** | 1.1× |
| **TTS pitch** | +5% |
| **Min duration** | 2000 ms |
| **Max duration** | 8000 ms |
| **Fade-out** | 500 ms |
| **Transition in/out** | 300 ms |

---

### 2.2 `amused`

| Właściwość | Wartość |
|-----------|---------|
| **Triggery** | Gracz zrobił coś zabawnego, sarkastyczny żart, ironia, mem kontekstowy |
| **Blendshapes** | `happy: 0.7`, `relaxed: 0.5` (asymetryczny uśmieszek) |
| **Aura color** | `#FFA500` (pomarańczowy) |
| **Aura intensity** | 0.5 |
| **Aura pulse** | tak, 1.0 Hz |
| **Head tilt** | 8° lewo (oś Z), bez oscylacji |
| **Body sway** | brak |
| **Entry animation** | brak |
| **TTS speed** | 1.05× |
| **TTS pitch** | +3% |
| **Min duration** | 2000 ms |
| **Max duration** | 6000 ms |
| **Fade-out** | 400 ms |
| **Transition in/out** | 250 ms |

---

### 2.3 `proud`

| Właściwość | Wartość |
|-----------|---------|
| **Triggery** | Wygenerowanie dokumentu, zakończenie raportu, sukces multi-step task, pochwała gracza |
| **Blendshapes** | `relaxed: 0.6`, `happy: 0.4` |
| **Aura color** | `#9B59B6` (fioletowy) |
| **Aura intensity** | 0.6 |
| **Aura pulse** | nie |
| **Head tilt** | 3° do tyłu (oś X — głowa lekko uniesiona) |
| **Body sway** | brak |
| **Entry animation** | płynne wyprostowanie się (spine +5° do tyłu, 300ms) |
| **TTS speed** | 1.0× |
| **TTS pitch** | −2% |
| **Min duration** | 2000 ms |
| **Max duration** | 7000 ms |
| **Fade-out** | 600 ms |
| **Transition in/out** | 350 ms |

---

### 2.4 `sympathetic`

| Właściwość | Wartość |
|-----------|---------|
| **Triggery** | Gracz przegrał, frustracja, długa sesja bez sukcesu, pytanie o pomoc emocjonalną |
| **Blendshapes** | `sad: 0.3`, `relaxed: 0.4` |
| **Aura color** | `#85C1E9` (jasnoniebieski) |
| **Aura intensity** | 0.4 |
| **Aura pulse** | nie |
| **Head tilt** | 10° lewo (oś Z), powolna oscylacja ±3°, 0.5 Hz |
| **Body sway** | brak |
| **Entry animation** | brak |
| **TTS speed** | 0.9× |
| **TTS pitch** | −3% |
| **Min duration** | 2000 ms |
| **Max duration** | 8000 ms |
| **Fade-out** | 700 ms |
| **Transition in/out** | 400 ms |

---

### 2.5 `sad`

| Właściwość | Wartość |
|-----------|---------|
| **Triggery** | LM Studio niedostępne, brak mikrofonu, poważny błąd systemu |
| **Blendshapes** | `sad: 1.0` |
| **Aura color** | `#2C3E50` (ciemnoniebieski) |
| **Aura intensity** | 0.4 |
| **Aura pulse** | nie |
| **Head tilt** | 15° w dół (oś X), bez oscylacji |
| **Body sway** | brak |
| **Entry animation** | powolne opuszczenie głowy (head tilt do −15° w 600ms) |
| **TTS speed** | 0.8× |
| **TTS pitch** | −5% |
| **Min duration** | 3000 ms |
| **Max duration** | 10000 ms |
| **Fade-out** | 800 ms |
| **Transition in/out** | 400 ms |

---

### 2.6 `disappointed`

| Właściwość | Wartość |
|-----------|---------|
| **Triggery** | Rate limit MCP, brak internetu, narzędzie nie pomogło, gracz zignorował radę |
| **Blendshapes** | `sad: 0.6`, `angry: 0.2` |
| **Aura color** | `#7F8C8D` (szary) |
| **Aura intensity** | 0.4 |
| **Aura pulse** | nie |
| **Head tilt** | 8° w dół (oś X) |
| **Body sway** | brak |
| **Entry animation** | brak |
| **TTS speed** | 0.85× |
| **TTS pitch** | −4% |
| **Min duration** | 2000 ms |
| **Max duration** | 6000 ms |
| **Fade-out** | 500 ms |
| **Transition in/out** | 300 ms |

---

### 2.7 `angry`

| Właściwość | Wartość |
|-----------|---------|
| **Triggery** | Użytkownik powtarza błąd wielokrotnie, ewidentna strata wartościowego itemu przez nieuwagę |
| **Blendshapes** | `angry: 1.0` |
| **Aura color** | `#E74C3C` (czerwony) |
| **Aura intensity** | 0.9 |
| **Aura pulse** | tak, 3.0 Hz |
| **Head tilt** | do przodu 5° (oś X), lekkie drżenie ±1° |
| **Body sway** | brak |
| **Entry animation** | krótkie szarpnięcie głowy (±3° X w 80ms, 2× bounce) |
| **TTS speed** | 1.1× |
| **TTS pitch** | +8% |
| **Min duration** | 1500 ms |
| **Max duration** | 5000 ms |
| **Fade-out** | 400 ms |
| **Transition in/out** | 200 ms |

---

### 2.8 `disgusted`

| Właściwość | Wartość |
|-----------|---------|
| **Triggery** | Słaby item "trash tier", spam bezużytecznych pytań, zła sytuacja w grze |
| **Blendshapes** | `angry: 0.5`, `sad: 0.3` (zmarszczony nos) |
| **Aura color** | `#27AE60` (ciemnozielony — kojarzony z niesmakiem) |
| **Aura intensity** | 0.5 |
| **Aura pulse** | nie |
| **Head tilt** | 8° w tył i 5° lewo (oś X+Z) |
| **Body sway** | brak |
| **Entry animation** | krótkie cofnięcie głowy (translateZ −0.03, 200ms) |
| **TTS speed** | 0.95× |
| **TTS pitch** | −2% |
| **Min duration** | 1500 ms |
| **Max duration** | 5000 ms |
| **Fade-out** | 400 ms |
| **Transition in/out** | 250 ms |

---

### 2.9 `excited`

| Właściwość | Wartość |
|-----------|---------|
| **Triggery** | Wykryto ulubioną grę, nowy sezon, rare boss kill, wyjątkowy drop |
| **Blendshapes** | `surprised: 0.8`, `happy: 0.7` |
| **Aura color** | `#F39C12` (jasnopomarańczowy) |
| **Aura intensity** | 1.0 |
| **Aura pulse** | tak, 3.0 Hz |
| **Head tilt** | ±5° oś Z, 3.0 Hz oscylacja |
| **Body sway** | ±5° oś Z, 2.5 Hz |
| **Entry animation** | translateY +0.1 (wyższe podskoczenie) → spring-back 500ms |
| **TTS speed** | 1.2× |
| **TTS pitch** | +10% |
| **Min duration** | 2000 ms |
| **Max duration** | 8000 ms |
| **Fade-out** | 400 ms |
| **Transition in/out** | 200 ms |

---

### 2.10 `scared`

| Właściwość | Wartość |
|-----------|---------|
| **Triggery** | Niebezpieczna sytuacja w grze (boss phase, deathly mechanic), VRAM exceeded |
| **Blendshapes** | `surprised: 0.5`, `sad: 0.4` |
| **Aura color** | `#8E44AD` (fioletowy ciemny) |
| **Aura intensity** | 0.8 |
| **Aura pulse** | tak, 4.0 Hz (szybkie) |
| **Head tilt** | cofnięcie 10° (oś X), dygotanie ±1° 8 Hz |
| **Body sway** | brak |
| **Entry animation** | szybkie cofnięcie (translateZ −0.05 w 100ms) |
| **TTS speed** | 1.3× |
| **TTS pitch** | +15% |
| **Min duration** | 1000 ms |
| **Max duration** | 4000 ms |
| **Fade-out** | 300 ms |
| **Transition in/out** | 150 ms |

---

### 2.11 `surprised`

| Właściwość | Wartość |
|-----------|---------|
| **Triggery** | Nieoczekiwany event w grze, pytanie o coś co asystent nie wiedział, nagłe zapytanie |
| **Blendshapes** | `surprised: 1.0` |
| **Aura color** | `#F8C471` (żółty jasny) |
| **Aura intensity** | 0.7 |
| **Aura pulse** | tak, 2.0 Hz (krótko, 1s) |
| **Head tilt** | do tyłu 8° (oś X) natychmiast |
| **Body sway** | brak |
| **Entry animation** | szybkie cofnięcie (translateZ −0.04 w 80ms) → powrót 300ms |
| **TTS speed** | 1.25× |
| **TTS pitch** | +12% |
| **Min duration** | 1000 ms |
| **Max duration** | 4000 ms |
| **Fade-out** | 300 ms |
| **Transition in/out** | 150 ms |

---

### 2.12 `nervous`

| Właściwość | Wartość |
|-----------|---------|
| **Triggery** | Długie oczekiwanie na LLM, kolejkowanie requestów, VRAM na granicy |
| **Blendshapes** | `sad: 0.3`, `surprised: 0.2` |
| **Aura color** | `#D4AC0D` (żółty matowy) |
| **Aura intensity** | 0.5 |
| **Aura pulse** | tak, 2.5 Hz |
| **Head tilt** | drobne dygotanie ±1.5° oś Z, 5 Hz |
| **Body sway** | brak |
| **Entry animation** | brak |
| **TTS speed** | 1.2× |
| **TTS pitch** | +5% |
| **Min duration** | 2000 ms |
| **Max duration** | 15000 ms (trwa przez czas oczekiwania) |
| **Fade-out** | 600 ms |
| **Transition in/out** | 300 ms |

---

### 2.13 `thinking`

| Właściwość | Wartość |
|-----------|---------|
| **Triggery** | LLM generuje odpowiedź, analiza złożonego pytania, multi-step tool use |
| **Blendshapes** | `relaxed: 0.5`, `lookUp: 0.4` (wzrok w górę — "myślę") |
| **Aura color** | `#5DADE2` (błękitny) |
| **Aura intensity** | 0.5 |
| **Aura pulse** | tak, 1.0 Hz (wolne, spokojne) |
| **Head tilt** | 5° w górę + 5° lewo (oś X+Z) |
| **Body sway** | ±1° oś Z, 0.5 Hz (minimalne) |
| **Entry animation** | płynne uniesienie głowy (300ms) |
| **TTS speed** | 0.85× |
| **TTS pitch** | −2% |
| **Min duration** | 1000 ms (czas generowania LLM) |
| **Max duration** | nieograniczony (trwa do zakończenia LLM) |
| **Fade-out** | 400 ms |
| **Transition in/out** | 350 ms |

**Uwaga:** `thinking` jest też stanem wizualnym systemu (sekcja 4) — blendshape thinking emocji i aura stanu systemu sumują się addytywnie.

---

### 2.14 `confused`

| Właściwość | Wartość |
|-----------|---------|
| **Triggery** | Niski confidence STT, niejasne pytanie, nieznana gra, VLM nie rozpoznaje sceny |
| **Blendshapes** | `surprised: 0.4`, `sad: 0.2` |
| **Aura color** | `#A9CCE3` (bladoniebies.) |
| **Aura intensity** | 0.45 |
| **Aura pulse** | nie |
| **Head tilt** | 12° lewo (oś Z) — charakterystyczny "tilted head" |
| **Body sway** | brak |
| **Entry animation** | powolny tilt głowy (12° w 500ms) |
| **TTS speed** | 0.9× |
| **TTS pitch** | +2% |
| **Min duration** | 2000 ms |
| **Max duration** | 8000 ms |
| **Fade-out** | 500 ms |
| **Transition in/out** | 400 ms |

---

### 2.15 `nostalgic`

| Właściwość | Wartość |
|-----------|---------|
| **Triggery** | Wspomnienie dawnych sezonów PoE, pytanie o stare mechamiki, długa historia sesji |
| **Blendshapes** | `sad: 0.3`, `relaxed: 0.5` |
| **Aura color** | `#F0E6D3` (kremowy, ciepły) |
| **Aura intensity** | 0.35 |
| **Aura pulse** | nie |
| **Head tilt** | 5° lewo, 3° w górę (oś X+Z — "patrzy w dal") |
| **Body sway** | ±1.5° oś Z, 0.4 Hz |
| **Entry animation** | brak (płynne przejście) |
| **TTS speed** | 0.8× |
| **TTS pitch** | −2% |
| **Min duration** | 2000 ms |
| **Max duration** | 10000 ms |
| **Fade-out** | 800 ms |
| **Transition in/out** | 500 ms |

---

### 2.16 `sarcastic`

| Właściwość | Wartość |
|-----------|---------|
| **Triggery** | Gracz zadaje oczywiste pytanie, ironia, żart na koszt oczywistego błędu |
| **Blendshapes** | `relaxed: 0.4`, `happy: 0.2` — asymetryczne (jeśli model wspiera lewą/prawą stronę twarzy osobno) |
| **Aura color** | `#BDC3C7` (srebrny) |
| **Aura intensity** | 0.4 |
| **Aura pulse** | nie |
| **Head tilt** | 5° lewo, minimalne uniesienie brwi (jeśli blendshape dostępny) |
| **Body sway** | brak |
| **Entry animation** | brak |
| **TTS speed** | 0.9× |
| **TTS pitch** | −3% |
| **Min duration** | 1500 ms |
| **Max duration** | 6000 ms |
| **Fade-out** | 400 ms |
| **Transition in/out** | 250 ms |

---

## 3. Emotion Lifecycle

### 3.1 Diagram stanów

```
           ┌─────────────────────────────────────────────────────┐
           │                    IDLE (neutral)                   │
           └────────────────────┬────────────────────────────────┘
                                │ LLM zwraca [EMO:xxx]
                                ▼
                    ┌──────── INCOMING ────────┐
                    │  Walidacja tagu          │
                    │  Resolve emotion config  │
                    └──────────┬───────────────┘
                               │ blend_in_ms
                               ▼
                    ┌──────── BLENDING IN ─────┐
                    │  Interpolacja blendshapes │
                    │  Ramp-up aury             │
                    │  Start body animation     │
                    └──────────┬───────────────┘
                               │ po blend_in_ms
                               ▼
                    ┌──────── HOLDING ─────────┐
                    │  Pełna ekspresja          │◄────── nowy [EMO:] → CONFLICT RESOLUTION
                    │  Timer: min–max duration  │
                    └──────────┬───────────────┘
                               │ po max_duration lub koniec TTS
                               ▼
                    ┌──────── FADING ──────────┐
                    │  Interpolacja → 0         │
                    │  fade_out_ms              │
                    └──────────┬───────────────┘
                               │
                               ▼
                            IDLE (neutral)
```

### 3.2 Implementacja TypeScript (szkielet)

```typescript
interface EmotionState {
  current: EmotionName;
  phase: "idle" | "blending_in" | "holding" | "fading";
  startedAt: number;
  config: EmotionConfig;
}

class EmotionController {
  private state: EmotionState = { current: "neutral", phase: "idle" };

  async transition(next: EmotionName): Promise<void> {
    if (this.state.phase !== "idle" && this.state.phase !== "fading") {
      await this.resolveConflict(next);
      return;
    }
    const config = EMOTIONS[next];
    this.state = { current: next, phase: "blending_in", startedAt: Date.now(), config };
    await this.blendIn(config);
    this.state.phase = "holding";
    await this.hold(config);
    this.state.phase = "fading";
    await this.fadeOut(config);
    this.state.phase = "idle";
  }
}
```

---

## 4. Conflict Resolution

Gdy nowa emocja nadchodzi podczas `HOLDING` lub `BLENDING_IN` poprzedniej:

| Priorytet nowej emocji vs. aktualnej | Zachowanie |
|--------------------------------------|------------|
| Wyższy (override_priority większy) | Natychmiastowy override — skróć fade-out aktualnej do 150ms, rozpocznij nową |
| Równy | Cross-fade: równoczesny fade-out aktualnej (300ms) + blend-in nowej (300ms) |
| Niższy | Kolejkowanie: nowa emocja zaczyna się po naturalnym zakończeniu aktualnej |

```python
EMOTION_PRIORITY: dict[str, int] = {
    "scared": 100,
    "angry": 90,
    "excited": 80,
    "surprised": 75,
    "sad": 60,
    "nervous": 55,
    "disappointed": 50,
    "disgusted": 50,
    "confused": 45,
    "happy": 40,
    "amused": 35,
    "proud": 35,
    "sympathetic": 30,
    "thinking": 25,
    "nostalgic": 20,
    "sarcastic": 20,
}
```

Emocje systemowo krytyczne (`scared`, `angry`) zawsze overridują.

---

## 5. Fallback Layers — Detekcja Capabilities

### 5.1 Algorytm przy ładowaniu modelu VRM

```typescript
interface ModelCapabilities {
  blendshapes: Record<string, boolean>;  // np. { "happy": true, "sad": true }
  hasFullHumanoid: boolean;              // czy VRMHumanoid ma LeftUpperArm etc.
  hasFingers: boolean;                   // LeftIndexProximal etc.
}

async function detectCapabilities(vrm: VRM): Promise<ModelCapabilities> {
  const em = vrm.expressionManager;
  const REQUIRED_BLENDSHAPES = [
    "happy", "sad", "angry", "surprised", "relaxed",
    "neutral", "aa", "ih", "ou", "ee", "oh",
    "blinkLeft", "blinkRight", "lookUp", "lookDown"
  ];

  const blendshapes: Record<string, boolean> = {};
  for (const name of REQUIRED_BLENDSHAPES) {
    blendshapes[name] = em !== null && em.getExpression(name) !== null;
  }

  const humanoid = vrm.humanoid;
  const hasFullHumanoid = humanoid !== null &&
    humanoid.getNormalizedBoneNode("leftUpperArm") !== null &&
    humanoid.getNormalizedBoneNode("rightUpperArm") !== null;

  return { blendshapes, hasFullHumanoid, hasFingers: false };
}
```

### 5.2 Zapis capabilities

Przy ładowaniu modelu zapisz do: `{content_root}/models/avatar/model_capabilities.json`

```json
{
  "model_file": "primary.vrm",
  "scanned_at": "2026-04-30T12:00:00",
  "blendshapes": {
    "happy": true, "sad": true, "angry": true,
    "surprised": true, "relaxed": true, "neutral": true,
    "aa": true, "ih": false, "ou": false, "ee": false, "oh": false,
    "blinkLeft": true, "blinkRight": true,
    "lookUp": true, "lookDown": true, "lookLeft": true, "lookRight": true
  },
  "hasFullHumanoid": true,
  "hasFingers": false
}
```

### 5.3 Fallback decyzja per frame

```typescript
function applyEmotion(emotion: EmotionName, capabilities: ModelCapabilities, weight: number): void {
  const config = EMOTIONS[emotion];

  // Layer 1: Blendshapes
  for (const [shape, value] of Object.entries(config.blendshapes)) {
    if (capabilities.blendshapes[shape]) {
      vrm.expressionManager?.setValue(shape, value * weight);
    }
  }

  // Layer 2: Aura (zawsze)
  setAura(config.aura, weight);

  // Layer 3: Body (jeśli dostępne)
  if (capabilities.hasFullHumanoid) {
    applyBodyAnimation(config.body, weight);
  }
}
```

---

## 6. System Visual States (niezależne od emocji)

Stany systemu nakładają się na emocje — addytywnie. Kolory aury są miksowane metodą HSL lerp.

| Stan | Trigger | Aura Color | Aura Intensity | Pulse Hz | Blendshape override | Body |
|------|---------|------------|----------------|----------|---------------------|------|
| `idle` | Brak aktywności | brak | 0.0 | — | brak | idle loop (oddychanie ±1°, 0.3 Hz) |
| `listening` | PTT wciśnięty lub wakeword aktywny | `#2ECC71` (zielony) | 0.8 | nie | brak | lekkie pochylenie do przodu 3° |
| `thinking` | LLM processing (po STT) | `#3498DB` (niebieski) | 0.6 | 1.0 Hz | brak | głowa lekko w górę 3° |
| `speaking` | TTS odtwarzany | `#F0F3F4` (biały) | 0.5 | nie | lip-sync aktywny | brak |
| `error` | Krytyczny błąd pipeline | `#E74C3C` (czerwony) | 1.0 | 2.0 Hz | `sad: 0.5` (force) | brak |
| `degraded` | LM Studio off / VRAM brak | `#F39C12` (żółty) | 0.7 | 0.5 Hz | `sad: 0.3` (force) | głowa opuszczona 5° |

### 6.1 Implementacja miksowania aury

```typescript
function mixAuraColors(
  emotionColor: string, emotionIntensity: number,
  stateColor: string, stateIntensity: number
): { color: string; intensity: number } {
  // HSL lerp: state ma wyższy priorytet gdy stateIntensity > 0.5
  const t = stateIntensity > 0.5 ? 0.7 : 0.3;
  return {
    color: lerpHSL(emotionColor, stateColor, t),
    intensity: Math.max(emotionIntensity, stateIntensity),
  };
}
```

### 6.2 Priorytet override blendshapes

`error` i `degraded` mają `force_blendshape: true` — nadpisują aktualną emocję LLM w Layer 1.

---

## 7. Lip-Sync

### 7.1 Algorytm

```
TTS audio stream (PCM 16kHz mono s16le)
        │
        ├── Okno 50ms (800 próbek przy 16kHz)
        │
        ├── RMS amplitude → wartość 0.0–1.0
        │     rms = sqrt(mean(samples^2)) / 32768
        │     normalized = clip(rms * 4.0, 0.0, 1.0)  # gain 4x
        │
        └── Mapowanie na blendshape `aa`:
              vrm.expressionManager.setValue("aa", normalized)
              Latency target: < 100ms od audio do animacji
```

### 7.2 Parametry

| Parametr | Wartość | Opis |
|----------|---------|------|
| Window size | 50 ms | Rozdzielczość czasowa lip-sync |
| Gain | 4.0× | Wzmocnienie RMS (głos syntezowany ma niższe RMS niż mowa naturalna) |
| Smoothing | 0.3 | Exponential moving average (zapobiega "migotaniu") |
| Latency target | < 100 ms | Od chunku audio do animacji |
| Primary blendshape | `aa` | Otwartość ust |

### 7.3 Rozszerzona wersja (opcjonalna, Phase 3)

Jeśli model ma `ih`, `ou`, `ee`, `oh` — użyj uproszczonej analizy formantów:

```python
PHONEME_MAP = {
    "aa": {"blendshape": "aa", "freq_range": (800, 1200)},
    "ih": {"blendshape": "ih", "freq_range": (300, 500)},
    "ou": {"blendshape": "ou", "freq_range": (400, 600)},
}
```

### 7.4 Wyłączenie lip-sync

W trybie cichym (`audio.silent_mode: true`): blendshape `aa` = 0.0 zawsze.

---

## 8. Emotion Tag Parser

### 8.1 Regex

```python
import re
from typing import Optional

EMOTION_TAG_PATTERN = re.compile(r"^\[EMO:([a-z_]+)\]\s*", re.IGNORECASE)

VALID_EMOTIONS = frozenset([
    "happy", "amused", "proud", "sympathetic",
    "sad", "disappointed", "angry", "disgusted",
    "excited", "scared", "surprised", "nervous",
    "thinking", "confused", "nostalgic", "sarcastic",
    "neutral",
])

def parse_emotion_tag(text: str) -> tuple[str, str]:
    """
    Zwraca (emotion_name, text_without_tag).
    Fallback: ("neutral", original_text) gdy tag nieprawidłowy lub brak.
    """
    match = EMOTION_TAG_PATTERN.match(text)
    if not match:
        return "neutral", text

    emotion = match.group(1).lower()
    remaining = text[match.end():]

    if emotion not in VALID_EMOTIONS:
        return "neutral", remaining  # nieznana emocja → neutral

    return emotion, remaining
```

### 8.2 Zachowanie dla edge cases

| Przypadek | Zachowanie |
|-----------|------------|
| Brak tagu | Użyj `persona.tts_emotion_bias` lub `"neutral"` |
| Nieznana emocja (np. `[EMO:cool]`) | Fallback `"neutral"`, log WARNING |
| Tag w środku tekstu | Ignoruj — parser patrzy tylko na początek |
| Wielokrotne tagi | Użyj pierwszego, ignoruj resztę |
| `[EMO:neutral]` jawnie | Akceptuj — resetuj do neutral |

---

## 9. Default Emotion Logic

```python
def resolve_default_emotion(
    parsed_emotion: Optional[str],
    persona_bias: str,
    system_state: str,
) -> str:
    """Priorytet: LLM tag > system_state override > persona_bias > neutral"""
    if parsed_emotion and parsed_emotion != "neutral":
        return parsed_emotion

    # System state może forceować emocję (error, degraded)
    STATE_FORCED_EMOTIONS = {
        "error": "sad",
        "degraded": "sad",
    }
    if system_state in STATE_FORCED_EMOTIONS:
        return STATE_FORCED_EMOTIONS[system_state]

    return persona_bias if persona_bias else "neutral"
```

---

## 10. TTS Modulation Reference

Pełna tabela speed/pitch per emocja. `formant_shift` zarezerwowany dla XTTSv2 (Piper go nie wspiera — zostaw `0`).

| Emocja | Speed | Pitch | Formant Shift |
|--------|-------|-------|---------------|
| `neutral` | 1.0× | 0% | 0 |
| `happy` | 1.1× | +5% | 0 |
| `amused` | 1.05× | +3% | 0 |
| `proud` | 1.0× | −2% | 0 |
| `sympathetic` | 0.9× | −3% | 0 |
| `sad` | 0.8× | −5% | 0 |
| `disappointed` | 0.85× | −4% | 0 |
| `angry` | 1.1× | +8% | 0 |
| `disgusted` | 0.95× | −2% | 0 |
| `excited` | 1.2× | +10% | 0 |
| `scared` | 1.3× | +15% | 0 |
| `surprised` | 1.25× | +12% | 0 |
| `nervous` | 1.2× | +5% | 0 |
| `thinking` | 0.85× | −2% | 0 |
| `confused` | 0.9× | +2% | 0 |
| `nostalgic` | 0.8× | −2% | 0 |
| `sarcastic` | 0.9× | −3% | 0 |

### 10.1 Zastosowanie w Piper

Piper CLI nie wspiera runtime pitch/speed adjustment per inference. Parametry są przekazywane przez modyfikację `length_scale` (speed inverse) i `noise_scale` z JSON config lub przez resampling audio po generacji.

```python
import soundfile as sf
import librosa

def apply_tts_modulation(
    audio_path: str, speed: float, pitch_percent: float, output_path: str
) -> None:
    audio, sr = sf.read(audio_path)
    if speed != 1.0:
        audio = librosa.effects.time_stretch(audio, rate=speed)
    if pitch_percent != 0:
        steps = pitch_percent / 100 * 12  # semitony
        audio = librosa.effects.pitch_shift(audio, sr=sr, n_steps=steps)
    sf.write(output_path, audio, sr)
```

---

## 11. `emotions.json` — Format Machine-Readable

Plik ładowany przez frontend przy starcie: `{content_root}/config/emotions.json`

```json
{
  "version": "1.0",
  "generated": "2026-04-30",
  "valid_names": [
    "happy", "amused", "proud", "sympathetic",
    "sad", "disappointed", "angry", "disgusted",
    "excited", "scared", "surprised", "nervous",
    "thinking", "confused", "nostalgic", "sarcastic",
    "neutral"
  ],
  "emotions": {
    "happy": {
      "priority": 40,
      "blendshapes": { "happy": 1.0, "relaxed": 0.3 },
      "aura": { "color": "#FFD700", "intensity": 0.7, "pulse": true, "pulse_hz": 1.5 },
      "body": {
        "head_tilt_z_deg": 5,
        "head_tilt_x_deg": 0,
        "oscillation_amplitude_deg": 2,
        "oscillation_hz": 1.5,
        "sway_amplitude_deg": 3,
        "sway_hz": 2.0,
        "entry": "bounce",
        "entry_translate_y": 0.06,
        "entry_spring_back_ms": 400
      },
      "tts": { "speed": 1.1, "pitch_percent": 5, "formant_shift": 0 },
      "timing": { "min_ms": 2000, "max_ms": 8000, "fade_out_ms": 500, "blend_in_ms": 300, "blend_out_ms": 300 }
    },
    "amused": {
      "priority": 35,
      "blendshapes": { "happy": 0.7, "relaxed": 0.5 },
      "aura": { "color": "#FFA500", "intensity": 0.5, "pulse": true, "pulse_hz": 1.0 },
      "body": { "head_tilt_z_deg": -8, "head_tilt_x_deg": 0, "oscillation_amplitude_deg": 0, "oscillation_hz": 0, "sway_amplitude_deg": 0, "sway_hz": 0, "entry": "none" },
      "tts": { "speed": 1.05, "pitch_percent": 3, "formant_shift": 0 },
      "timing": { "min_ms": 2000, "max_ms": 6000, "fade_out_ms": 400, "blend_in_ms": 250, "blend_out_ms": 250 }
    },
    "proud": {
      "priority": 35,
      "blendshapes": { "relaxed": 0.6, "happy": 0.4 },
      "aura": { "color": "#9B59B6", "intensity": 0.6, "pulse": false, "pulse_hz": 0 },
      "body": { "head_tilt_z_deg": 0, "head_tilt_x_deg": -3, "oscillation_amplitude_deg": 0, "oscillation_hz": 0, "sway_amplitude_deg": 0, "sway_hz": 0, "entry": "straighten" },
      "tts": { "speed": 1.0, "pitch_percent": -2, "formant_shift": 0 },
      "timing": { "min_ms": 2000, "max_ms": 7000, "fade_out_ms": 600, "blend_in_ms": 350, "blend_out_ms": 350 }
    },
    "sympathetic": {
      "priority": 30,
      "blendshapes": { "sad": 0.3, "relaxed": 0.4 },
      "aura": { "color": "#85C1E9", "intensity": 0.4, "pulse": false, "pulse_hz": 0 },
      "body": { "head_tilt_z_deg": -10, "head_tilt_x_deg": 0, "oscillation_amplitude_deg": 3, "oscillation_hz": 0.5, "sway_amplitude_deg": 0, "sway_hz": 0, "entry": "none" },
      "tts": { "speed": 0.9, "pitch_percent": -3, "formant_shift": 0 },
      "timing": { "min_ms": 2000, "max_ms": 8000, "fade_out_ms": 700, "blend_in_ms": 400, "blend_out_ms": 400 }
    },
    "sad": {
      "priority": 60,
      "blendshapes": { "sad": 1.0 },
      "aura": { "color": "#2C3E50", "intensity": 0.4, "pulse": false, "pulse_hz": 0 },
      "body": { "head_tilt_z_deg": 0, "head_tilt_x_deg": 15, "oscillation_amplitude_deg": 0, "oscillation_hz": 0, "sway_amplitude_deg": 0, "sway_hz": 0, "entry": "droop" },
      "tts": { "speed": 0.8, "pitch_percent": -5, "formant_shift": 0 },
      "timing": { "min_ms": 3000, "max_ms": 10000, "fade_out_ms": 800, "blend_in_ms": 400, "blend_out_ms": 400 }
    },
    "disappointed": {
      "priority": 50,
      "blendshapes": { "sad": 0.6, "angry": 0.2 },
      "aura": { "color": "#7F8C8D", "intensity": 0.4, "pulse": false, "pulse_hz": 0 },
      "body": { "head_tilt_z_deg": 0, "head_tilt_x_deg": 8, "oscillation_amplitude_deg": 0, "oscillation_hz": 0, "sway_amplitude_deg": 0, "sway_hz": 0, "entry": "none" },
      "tts": { "speed": 0.85, "pitch_percent": -4, "formant_shift": 0 },
      "timing": { "min_ms": 2000, "max_ms": 6000, "fade_out_ms": 500, "blend_in_ms": 300, "blend_out_ms": 300 }
    },
    "angry": {
      "priority": 90,
      "blendshapes": { "angry": 1.0 },
      "aura": { "color": "#E74C3C", "intensity": 0.9, "pulse": true, "pulse_hz": 3.0 },
      "body": { "head_tilt_z_deg": 0, "head_tilt_x_deg": -5, "oscillation_amplitude_deg": 1, "oscillation_hz": 8, "sway_amplitude_deg": 0, "sway_hz": 0, "entry": "shake" },
      "tts": { "speed": 1.1, "pitch_percent": 8, "formant_shift": 0 },
      "timing": { "min_ms": 1500, "max_ms": 5000, "fade_out_ms": 400, "blend_in_ms": 200, "blend_out_ms": 200 }
    },
    "disgusted": {
      "priority": 50,
      "blendshapes": { "angry": 0.5, "sad": 0.3 },
      "aura": { "color": "#27AE60", "intensity": 0.5, "pulse": false, "pulse_hz": 0 },
      "body": { "head_tilt_z_deg": -5, "head_tilt_x_deg": -8, "oscillation_amplitude_deg": 0, "oscillation_hz": 0, "sway_amplitude_deg": 0, "sway_hz": 0, "entry": "recoil" },
      "tts": { "speed": 0.95, "pitch_percent": -2, "formant_shift": 0 },
      "timing": { "min_ms": 1500, "max_ms": 5000, "fade_out_ms": 400, "blend_in_ms": 250, "blend_out_ms": 250 }
    },
    "excited": {
      "priority": 80,
      "blendshapes": { "surprised": 0.8, "happy": 0.7 },
      "aura": { "color": "#F39C12", "intensity": 1.0, "pulse": true, "pulse_hz": 3.0 },
      "body": { "head_tilt_z_deg": 5, "head_tilt_x_deg": 0, "oscillation_amplitude_deg": 5, "oscillation_hz": 3.0, "sway_amplitude_deg": 5, "sway_hz": 2.5, "entry": "jump", "entry_translate_y": 0.1, "entry_spring_back_ms": 500 },
      "tts": { "speed": 1.2, "pitch_percent": 10, "formant_shift": 0 },
      "timing": { "min_ms": 2000, "max_ms": 8000, "fade_out_ms": 400, "blend_in_ms": 200, "blend_out_ms": 200 }
    },
    "scared": {
      "priority": 100,
      "blendshapes": { "surprised": 0.5, "sad": 0.4 },
      "aura": { "color": "#8E44AD", "intensity": 0.8, "pulse": true, "pulse_hz": 4.0 },
      "body": { "head_tilt_z_deg": 0, "head_tilt_x_deg": -10, "oscillation_amplitude_deg": 1.5, "oscillation_hz": 8, "sway_amplitude_deg": 0, "sway_hz": 0, "entry": "recoil_fast" },
      "tts": { "speed": 1.3, "pitch_percent": 15, "formant_shift": 0 },
      "timing": { "min_ms": 1000, "max_ms": 4000, "fade_out_ms": 300, "blend_in_ms": 150, "blend_out_ms": 150 }
    },
    "surprised": {
      "priority": 75,
      "blendshapes": { "surprised": 1.0 },
      "aura": { "color": "#F8C471", "intensity": 0.7, "pulse": true, "pulse_hz": 2.0 },
      "body": { "head_tilt_z_deg": 0, "head_tilt_x_deg": -8, "oscillation_amplitude_deg": 0, "oscillation_hz": 0, "sway_amplitude_deg": 0, "sway_hz": 0, "entry": "recoil" },
      "tts": { "speed": 1.25, "pitch_percent": 12, "formant_shift": 0 },
      "timing": { "min_ms": 1000, "max_ms": 4000, "fade_out_ms": 300, "blend_in_ms": 150, "blend_out_ms": 150 }
    },
    "nervous": {
      "priority": 55,
      "blendshapes": { "sad": 0.3, "surprised": 0.2 },
      "aura": { "color": "#D4AC0D", "intensity": 0.5, "pulse": true, "pulse_hz": 2.5 },
      "body": { "head_tilt_z_deg": 0, "head_tilt_x_deg": 0, "oscillation_amplitude_deg": 1.5, "oscillation_hz": 5, "sway_amplitude_deg": 0, "sway_hz": 0, "entry": "none" },
      "tts": { "speed": 1.2, "pitch_percent": 5, "formant_shift": 0 },
      "timing": { "min_ms": 2000, "max_ms": 15000, "fade_out_ms": 600, "blend_in_ms": 300, "blend_out_ms": 300 }
    },
    "thinking": {
      "priority": 25,
      "blendshapes": { "relaxed": 0.5, "lookUp": 0.4 },
      "aura": { "color": "#5DADE2", "intensity": 0.5, "pulse": true, "pulse_hz": 1.0 },
      "body": { "head_tilt_z_deg": -5, "head_tilt_x_deg": -5, "oscillation_amplitude_deg": 1, "oscillation_hz": 0.5, "sway_amplitude_deg": 1, "sway_hz": 0.5, "entry": "lookup" },
      "tts": { "speed": 0.85, "pitch_percent": -2, "formant_shift": 0 },
      "timing": { "min_ms": 1000, "max_ms": 99999, "fade_out_ms": 400, "blend_in_ms": 350, "blend_out_ms": 350 }
    },
    "confused": {
      "priority": 45,
      "blendshapes": { "surprised": 0.4, "sad": 0.2 },
      "aura": { "color": "#A9CCE3", "intensity": 0.45, "pulse": false, "pulse_hz": 0 },
      "body": { "head_tilt_z_deg": -12, "head_tilt_x_deg": 0, "oscillation_amplitude_deg": 0, "oscillation_hz": 0, "sway_amplitude_deg": 0, "sway_hz": 0, "entry": "tilt_slow" },
      "tts": { "speed": 0.9, "pitch_percent": 2, "formant_shift": 0 },
      "timing": { "min_ms": 2000, "max_ms": 8000, "fade_out_ms": 500, "blend_in_ms": 400, "blend_out_ms": 400 }
    },
    "nostalgic": {
      "priority": 20,
      "blendshapes": { "sad": 0.3, "relaxed": 0.5 },
      "aura": { "color": "#F0E6D3", "intensity": 0.35, "pulse": false, "pulse_hz": 0 },
      "body": { "head_tilt_z_deg": -5, "head_tilt_x_deg": -3, "oscillation_amplitude_deg": 1.5, "oscillation_hz": 0.4, "sway_amplitude_deg": 1.5, "sway_hz": 0.4, "entry": "none" },
      "tts": { "speed": 0.8, "pitch_percent": -2, "formant_shift": 0 },
      "timing": { "min_ms": 2000, "max_ms": 10000, "fade_out_ms": 800, "blend_in_ms": 500, "blend_out_ms": 500 }
    },
    "sarcastic": {
      "priority": 20,
      "blendshapes": { "relaxed": 0.4, "happy": 0.2 },
      "aura": { "color": "#BDC3C7", "intensity": 0.4, "pulse": false, "pulse_hz": 0 },
      "body": { "head_tilt_z_deg": -5, "head_tilt_x_deg": 0, "oscillation_amplitude_deg": 0, "oscillation_hz": 0, "sway_amplitude_deg": 0, "sway_hz": 0, "entry": "none" },
      "tts": { "speed": 0.9, "pitch_percent": -3, "formant_shift": 0 },
      "timing": { "min_ms": 1500, "max_ms": 6000, "fade_out_ms": 400, "blend_in_ms": 250, "blend_out_ms": 250 }
    },
    "neutral": {
      "priority": 0,
      "blendshapes": { "neutral": 1.0 },
      "aura": { "color": "#FFFFFF", "intensity": 0.0, "pulse": false, "pulse_hz": 0 },
      "body": { "head_tilt_z_deg": 0, "head_tilt_x_deg": 0, "oscillation_amplitude_deg": 0, "oscillation_hz": 0, "sway_amplitude_deg": 1, "sway_hz": 0.3, "entry": "none" },
      "tts": { "speed": 1.0, "pitch_percent": 0, "formant_shift": 0 },
      "timing": { "min_ms": 0, "max_ms": 99999, "fade_out_ms": 300, "blend_in_ms": 300, "blend_out_ms": 300 }
    }
  },
  "visual_states": {
    "idle": { "aura_color": null, "aura_intensity": 0.0, "pulse": false, "force_blendshape": null },
    "listening": { "aura_color": "#2ECC71", "aura_intensity": 0.8, "pulse": false, "force_blendshape": null },
    "thinking": { "aura_color": "#3498DB", "aura_intensity": 0.6, "pulse": true, "pulse_hz": 1.0, "force_blendshape": null },
    "speaking": { "aura_color": "#F0F3F4", "aura_intensity": 0.5, "pulse": false, "force_blendshape": null },
    "error": { "aura_color": "#E74C3C", "aura_intensity": 1.0, "pulse": true, "pulse_hz": 2.0, "force_blendshape": "sad", "force_blendshape_value": 0.5 },
    "degraded": { "aura_color": "#F39C12", "aura_intensity": 0.7, "pulse": true, "pulse_hz": 0.5, "force_blendshape": "sad", "force_blendshape_value": 0.3 }
  }
}
```

---

## 12. Test Fixtures

### 12.1 Oczekiwana capabilities matrix per model VRM

| Model | `happy` | `sad` | `angry` | `surprised` | `relaxed` | `aa`–`oh` | Full Humanoid |
|-------|---------|-------|---------|-------------|-----------|-----------|---------------|
| VRoid Team sample (primary) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| VRoid Team sample (fallback) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Minimalny placeholder | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

Dla modelu minimalnego: **wszystkie emocje przez aura + body** (Layer 2+3 only).

### 12.2 Test cases

| Test ID | Input | Oczekiwane |
|---------|-------|-----------|
| EMO-01 | `[EMO:happy]` | happy blendshape = 1.0, aura = `#FFD700`, speed = 1.1× |
| EMO-02 | `[EMO:unknown_tag]` | fallback neutral, log WARNING |
| EMO-03 | Brak tagu w odpowiedzi | `persona.tts_emotion_bias` lub neutral |
| EMO-04 | `[EMO:scared]` podczas `[EMO:amused]` | override (scared priorytet 100 > amused 35) |
| EMO-05 | Model bez blendshapes | aura + body działają, brak blendshape error |
| EMO-06 | TTS audio chunk 50ms | lip-sync aa = RMS * 4.0 * smoothing |
| EMO-07 | System state `error` | aura `#E74C3C`, force `sad: 0.5`, niezależnie od emocji LLM |

---

*Dokument: DOK-06 EMOTION_SPEC.md v1.0 — 2026-04-30*
*Następny: DOK-07 COMMANDS_SPEC.md*
