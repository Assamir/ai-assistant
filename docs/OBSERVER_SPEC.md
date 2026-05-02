# DOK-09: OBSERVER_SPEC.md — Specyfikacja Trybu Obserwatora

> **Status:** v1.0 — 2026-04-30
> **Materiały źródłowe:** PRD_02_FUNCTIONAL.md (§4), DB_SCHEMA.md, DECISIONS_LOG.md (DOK-09)

---

## Reguły naczelne

| # | Reguła | Materializacja |
|---|--------|---------------|
| 7 | User interaction priority | PTT/wakeword pauzuje observer loop natychmiast |
| 2 | Twardy sandbox | Screenshoty tylko in-memory, brak zapisu (chyba że debug) |

---

## 1. Trzy Typy Obserwatora

| Typ | Trigger | Lifecycle | Output | DB |
|-----|---------|-----------|--------|-----|
| **Game Observer** | Komenda "Zacznij obserwować" po auto-detekcji gry | Pętla co N sekund, aktywna do stopu | Komentarz głosowy, `messages(source='observer')` | `game_detections`, `messages` |
| **On-demand Query** | STT: "Co widzisz?", "Jaki to item?", etc. | Jednorazowy capture, zakończony po odpowiedzi | Odpowiedź w konwersacji (source='assistant') | `messages` |
| **Ambient Observer** | Pytanie o ekran poza kontekstem gry | Jednorazowy (jak on-demand), domyślnie wyłączony | Odpowiedź w konwersacji | `messages` |

### 1.1 Diagram — Game Observer lifecycle

```
User: "Zacznij obserwować"
        │
        ▼
GameDetector.current_game() → game_profile.yaml ładowany
        │
        ├─ brak gry → TTS "Nie widzę aktywnej gry"
        │
        ▼
ObserverLoop.start(interval=game_profile.observer_interval_seconds)
        │
        ▼ co N sekund:
        ├─ PTT aktywny? → skip cycle
        ├─ sleep_mode? → skip
        ├─ scene_hash identyczny × 3? → skip
        │
        ▼
Capture → VLM → [OCR] → Comment → TTS → DB
        │
User: "Przestań obserwować"
        │
        ▼
ObserverLoop.stop() → game_detections.ended_at = now
```

---

## 2. Game Detection — Algorytm Kaskadowy

### 2.1 Krok 1: psutil process scan (co 5s, background)

```python
import psutil
from pathlib import Path

async def detect_game_by_process(game_profiles: list[GameProfile]) -> Optional[GameProfile]:
    running = {p.name().lower() for p in psutil.process_iter(["name"])}
    for profile in game_profiles:
        for proc_name in profile.process_names:
            if proc_name.lower() in running:
                return profile
    return None
```

### 2.2 Krok 2: VLM fallback (gdy obserwator aktywny bez detekcji procesu)

```python
async def detect_game_by_vlm(vlm: VLMEngine, frame: np.ndarray) -> Optional[str]:
    description = await vlm.describe(frame,
        prompt="Is this a video game? If yes, what game is it? Answer in English, one sentence.")
    # Prosty parsing: "This appears to be Path of Exile 2" → "poe2"
    return match_game_name_from_text(description)
```

### 2.3 Krok 3: Manual override

Komenda "Gram teraz w PoE2" → `GameDetector.set_manual_override("poe2")`.

### 2.4 Disambiguation

Jeśli ≥2 gry wykryte jednocześnie: użyj pierwszej znalezionej (według kolejności w `game_profiles/`) + log WARNING. Użytkownik może ręcznie overridować.

### 2.5 Persistence w DB

```sql
INSERT INTO game_detections (game_id, game_name, detection_method, started_at)
VALUES ('poe2', 'Path of Exile 2', 'process', unixepoch());
-- przy stopie:
UPDATE game_detections SET ended_at = unixepoch() WHERE id = ?;
```

---

## 3. Game Profiles — Schema YAML

```python
from pydantic import BaseModel, Field
from typing import Optional

class ScreenRegion(BaseModel):
    name: str
    position: str           # "bottom-left", "top-right", etc.
    size_percent: int       # procent ekranu (np. 15)

class GameProfile(BaseModel):
    id: str                 # np. "poe2" — klucz pliku
    name: str               # pełna nazwa
    process_names: list[str]
    observer_type: str      # "action" | "strategic" | "exploration"
    observer_interval_seconds: int = Field(ge=5, le=300, default=10)
    focus_areas: list[str]
    screen_regions: list[ScreenRegion] = []
    context_prompt: str     # wstrzykiwany do GAME_PROFILE sekcji systemu
    vlm_prompt_template: str = "Opisz scenę z gry {game_name}. Skup się na: {focus_areas}."
    mcp_sources: list[str] = []
    ocr_enabled: bool       # per DECISIONS_LOG DOK-09 #3
    comment_styles: list[str] = []      # wzorce komentarzy do losowania (urozmaicenie)
    silence_after_comment_seconds: int = 30
```

### 3.1 Przykład: `poe2.yaml`

```yaml
id: poe2
name: "Path of Exile 2"
process_names:
  - "PathOfExile_x64.exe"
  - "PathOfExileSteam.exe"
observer_type: action
observer_interval_seconds: 5
focus_areas:
  - builds
  - loot
  - combat
  - boss_mechanics
screen_regions:
  - name: health_mana
    position: bottom-left
    size_percent: 15
  - name: minimap
    position: top-right
    size_percent: 15
context_prompt: |
  Jesteś ekspertem od Path of Exile 2. Skupiaj się na:
  - Analizie przedmiotów (affixy, tier, wartość)
  - Ostrzeganiu przed niebezpiecznymi mechanikami
  - Sugestiach dotyczących buildu gracza
  - Wykrywaniu rzadkich dropów
vlm_prompt_template: >
  To jest zrzut ekranu z Path of Exile 2.
  Opisz co widzisz: stan gracza, UI, walka, inventory.
  Szczególnie zwróć uwagę na: {focus_areas}.
  Odpowiedz po polsku, max 3 zdania.
mcp_sources:
  - "poe2.wiki.gg"
  - "maxroll.gg/poe2"
ocr_enabled: true
comment_styles:
  - "Krótki alert (jedno zdanie)"
  - "Komentarz buildera (analiza mechaniki)"
  - "Sarkastyczna obserwacja (jeśli gracz zignorował oczywistą mechnikę)"
silence_after_comment_seconds: 20
```

### 3.2 Przykład: `stellaris.yaml`

```yaml
id: stellaris
name: "Stellaris"
process_names:
  - "stellaris.exe"
observer_type: strategic
observer_interval_seconds: 15
focus_areas:
  - diplomacy
  - fleet_strength
  - economy
  - research
  - crisis_events
screen_regions:
  - name: resource_bar
    position: top
    size_percent: 5
  - name: main_map
    position: center
    size_percent: 70
context_prompt: |
  Jesteś doradcą strategicznym w Stellaris. Analizujesz sytuację galaktyczną:
  - Dyplomacja i sojusze
  - Stan floty względem rywali
  - Priorytety badań i ekonomii
  - Zagrożenia kryzysu mid/end-game
vlm_prompt_template: >
  To jest zrzut ekranu ze Stellaris.
  Opisz co widzisz: stan imperium, aktywne okna, mapa.
  Skup się na: {focus_areas}.
  Jeśli nic istotnego — powiedz "[SKIP]".
ocr_enabled: false
silence_after_comment_seconds: 30
```

---

## 4. Capture Pipeline

### 4.1 DXcam config

```python
import dxcam

camera = dxcam.create(
    output_idx=None,         # None = aktywny monitor gry (via pygetwindow)
    output_color="RGB",
    max_buffer_len=2,        # minimalne buffering
)
# Observer capture: 1 FPS (brak ciągłego stream)
frame = camera.grab(region=None)  # cały monitor

# Jeśli game_profile.screen_regions → crop po capturze
def crop_region(frame, region: ScreenRegion, monitor_size: tuple) -> np.ndarray:
    w, h = monitor_size
    margin = region.size_percent / 100
    positions = {
        "bottom-left": (0, int(h * (1 - margin)), int(w * margin), h),
        "top-right": (int(w * (1 - margin)), 0, w, int(h * margin)),
        "top": (0, 0, w, int(h * margin)),
        "center": (int(w * 0.15), int(h * 0.15), int(w * 0.85), int(h * 0.85)),
    }
    x1, y1, x2, y2 = positions[region.position]
    return frame[y1:y2, x1:x2]
```

### 4.2 Monitor detection

```python
import pygetwindow as gw

def find_game_monitor(process_name: str) -> Optional[int]:
    """Zwraca indeks monitora na którym okno gry się znajduje."""
    windows = gw.getWindowsWithTitle("")
    for win in windows:
        if process_name.lower() in win.title.lower():
            # Mapuj pozycję okna na indeks monitora (heurystyka)
            return monitor_at(win.left, win.top)
    return None  # fallback: config.observer.monitor_index
```

### 4.3 Frame storage

Screenshoty in-memory only (`np.ndarray`). Brak zapisu na dysk. Wyjątek: `config.debug.save_screenshots = true` → zapis do `logs/debug_screenshots/` z timestamp.

---

## 5. VLM Pipeline

### 5.1 Moondream2 call

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

class Moondream2VLM:
    def __init__(self, model_path: str):
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path, trust_remote_code=True,
            torch_dtype=torch.float16, device_map="cuda"
        )
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)

    async def describe(self, frame: np.ndarray, prompt: str) -> str:
        from PIL import Image
        import asyncio
        image = Image.fromarray(frame)
        loop = asyncio.get_event_loop()
        # Moondream2 jest synchroniczny — run w executor
        return await loop.run_in_executor(None, self._run, image, prompt)

    def _run(self, image, prompt: str) -> str:
        enc = self.model.encode_image(image)
        return self.model.answer_question(enc, prompt, self.tokenizer)
```

### 5.2 Trigger OCR

VLM output → sprawdź keywords:
```python
OCR_TRIGGER_KEYWORDS = [
    "tooltip", "item", "inventory", "stat", "damage", "tier",
    "prefix", "suffix", "affix", "modifier", "equipment"
]

def should_run_ocr(vlm_output: str) -> bool:
    text_lower = vlm_output.lower()
    return any(kw in text_lower for kw in OCR_TRIGGER_KEYWORDS)
```

---

## 6. OCR Pipeline

### 6.1 EasyOCR config

```python
import easyocr

reader = easyocr.Reader(
    ["en"],   # tylko angielski (game UI jest EN nawet w grze z PL)
    gpu=True,
    model_storage_directory=str(content_root / "models" / "easyocr"),
)

async def run_ocr(frame: np.ndarray) -> str:
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, reader.readtext, frame)
    # Filtruj noise: token długości < 2, confidence < 0.3
    texts = [r[1] for r in results if len(r[1]) >= 2 and r[2] >= 0.3]
    return "\n".join(texts)
```

### 6.2 Per-profile `ocr_enabled`

- `poe2.yaml`: `ocr_enabled: true` — action game z drobnym UI tekstu
- `stellaris.yaml`: `ocr_enabled: false` — strategic, VLM wystarczy
- Konfigurowalny override: `config.observer.ocr_force_enabled`

---

## 7. Comment Generation

### 7.1 Prompt do LLM

Z DOK-05 `PROMPT_SPEC.md` — Observer Comment Prompt (sekcja 5). Interpolowany:

```python
def build_observer_prompt(
    scene_description: str, ocr_text: str,
    last_comment: str, game_profile: GameProfile,
    player_profile: Optional[PlayerProfile],
) -> str:
    ocr_section = f"\nTEKST Z EKRANU (OCR):\n{ocr_text}" if ocr_text.strip() else ""
    character_section = ""
    if player_profile:
        char = player_profile.active_character
        if char:
            character_section = f"\nAKTYWNA POSTAĆ: {char.name} ({char.char_class}, {char.build})"
    return OBSERVER_PROMPT_TEMPLATE.format(
        scene_description=scene_description,
        ocr_text_if_any=ocr_section,
        last_observer_comment=last_comment,
        game_name=game_profile.name,
        game_context_prompt=game_profile.context_prompt + character_section,
    )
```

### 7.2 Diversity check (cosine similarity)

```python
async def is_too_similar_to_recent(
    new_comment: str, recent_comments: list[str],
    embedder: SentenceTransformer, threshold: float = 0.85,
) -> bool:
    if not recent_comments:
        return False
    new_emb = embedder.encode(new_comment)
    recent_embs = embedder.encode(recent_comments[-3:])
    similarities = cosine_similarity([new_emb], recent_embs)[0]
    return float(max(similarities)) > threshold
```

### 7.3 Silence cooldown

```python
class CommentRateLimiter:
    def __init__(self, silence_seconds: int = 30):
        self._last_comment_at: float = 0
        self._silence = silence_seconds

    def can_comment(self) -> bool:
        return time.monotonic() - self._last_comment_at >= self._silence

    def mark_commented(self):
        self._last_comment_at = time.monotonic()
```

---

## 8. On-demand Screen Query

### 8.1 Trigger patterns (z COMMANDS_SPEC)

Komendy nie mają dedykowanego CMD-ID — klasyfikowane przez LLM intent z promptem "co widzisz?", "jaki to item?", "co jest na ekranie?", "wytłumacz mi tę stronę".

Backend: LLM wywołuje tool `screen_capture(focus_cursor=True, prompt="...")`.

### 8.2 Capture i analiza

```python
async def on_demand_query(prompt: str) -> dict:
    import pyautogui
    cursor_x, cursor_y = pyautogui.position()

    # Full screenshot
    frame = await screen_capture_service.capture()

    # Crop 600×400 wokół kursora
    x1 = max(0, cursor_x - 300)
    y1 = max(0, cursor_y - 200)
    x2 = min(frame.shape[1], cursor_x + 300)
    y2 = min(frame.shape[0], cursor_y + 200)
    cursor_crop = frame[y1:y2, x1:x2]

    vlm_prompt = f"Kursor na pozycji ({cursor_x},{cursor_y}). {prompt}"
    description = await vlm.describe(frame, vlm_prompt)

    ocr_text = ""
    if should_run_ocr(description):
        ocr_text = await run_ocr(cursor_crop)

    return {"description": description, "ocr_text": ocr_text}
```

**Nie zapisuj w `game_detections`** — on-demand query to część konwersacji, nie observer session.

---

## 9. Pause/Resume

```python
class ObserverPauseManager:
    GRACE_PERIOD_S = 2.0

    async def pause_for_interaction(self, observer: ObserverLoop):
        await observer.pause()

    async def resume_after_interaction(self, observer: ObserverLoop):
        await asyncio.sleep(self.GRACE_PERIOD_S)
        await observer.resume()

# Wbudowane triggery pauzy:
# - PTT start → pause
# - Conversation lock (LLM processing) → pause
# - PTT end / Conversation unlock → schedule resume po GRACE_PERIOD
```

---

## 10. Lifecycle Events (DB)

```python
# Start obserwatora
await db.execute(
    "INSERT INTO game_detections (game_id, game_name, detection_method, started_at) VALUES (?,?,?,unixepoch())",
    (profile.id, profile.name, "process")
)

# Każdy komentarz
await db.execute(
    "INSERT INTO messages (session_id, source, content, emotion, scene_hash) VALUES (?,?,?,?,?)",
    (session_id, "observer", comment.text, comment.emotion, scene_hash)
)

# Snapshot kontekstu
await db.execute(
    "INSERT INTO player_context_snapshots (session_id, game_id, snapshot_json, trigger_event) VALUES (?,?,?,?)",
    (session_id, profile.id, json.dumps(player_snapshot), "game_detected")
)

# Stop obserwatora
await db.execute(
    "UPDATE game_detections SET ended_at = unixepoch() WHERE game_id = ? AND ended_at IS NULL",
    (profile.id,)
)
```

---

## 11. Error Handling

| Błąd | Zachowanie |
|------|------------|
| DXcam fail (exclusive fullscreen) | Fallback do `mss` library + log WARNING |
| VLM timeout > 10s | Skip cycle, brak komunikatu |
| VLM timeout × 3 z rzędu | Emocja `nervous`, log ERROR |
| OCR fail | Kontynuuj z samym VLM output |
| Game process zamknął się | Emocja `surprised`, TTS "Wygląda na koniec gry!", stop observer |
| DXcam crash (brak monitora) | Stop observer + log CRITICAL + TTS "Straciłem dostęp do ekranu" |

---

## 12. Performance Targets

| Metryka | Target |
|---------|--------|
| FPS impact | < 5% (z PRD_03) |
| Capture latency | < 100ms |
| VLM latency | < 5s (Moondream2 na RTX 5090) |
| Full cycle (capture→comment) | < 5s |
| OCR latency | < 1s |

**Tuning:** obserwator używa priority 4 w GPU Scheduler — najniższy, nie rywalizuje z interakcją.

---

*Dokument: DOK-09 OBSERVER_SPEC.md v1.0 — 2026-04-30*
*Następny: DOK-10 MCP_TOOLS_SPEC.md*
