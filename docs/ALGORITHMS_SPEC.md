# DOK-08: ALGORITHMS_SPEC.md — Specyfikacja Algorytmów Krytycznych

> **Status:** v1.0 — 2026-04-30
> **Materiały źródłowe:** PRD_03_NONFUNCTIONAL.md (GPU Scheduler, priorytety), PRD_01_VISION.md (Circuit Breaker), PRD_02_FUNCTIONAL.md (Cache, Rate Limiter), DB_SCHEMA.md

---

## 1. GPU Scheduler (Priority Lock)

### 1.1 Cel

Żadne dwa inference modeli AI nie wykonują się równocześnie na GPU. Kolejność: STT > LLM > TTS > VLM.

### 1.2 Priorytety

| Priorytet | Operacja | Uzasadnienie |
|-----------|----------|-------------|
| 1 (najwyższy) | STT (transkrypcja PTT/wakeword) | Responsywność — użytkownik czeka na feedback |
| 2 | LLM (generowanie odpowiedzi) | Użytkownik czeka |
| 3 | TTS (generowanie audio) | Może być CPU; GPU opcjonalne |
| 4 (najniższy) | VLM (observer loop) | Background, nie time-critical |

### 1.3 Implementacja

```python
import asyncio
import heapq
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

@dataclass(order=True)
class ScheduledTask:
    priority: int                      # niższy = wyższy priorytet (heap min)
    enqueued_at: float = field(compare=False, default_factory=time.monotonic)
    task_id: str = field(compare=False, default="")
    coro: Coroutine = field(compare=False, default=None)
    timeout_s: float = field(compare=False, default=60.0)

class GPUScheduler:
    """asyncio-based priority queue z mutex dla GPU."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._queue: list[ScheduledTask] = []
        self._running = False
        self._metrics = {"wait_times": [], "queue_depth": 0}
        self._aging_task: asyncio.Task | None = None

    async def submit(self, coro: Coroutine, priority: int,
                     task_id: str = "", timeout_s: float = 60.0) -> Any:
        task = ScheduledTask(priority=priority, task_id=task_id,
                             coro=coro, timeout_s=timeout_s)
        heapq.heappush(self._queue, task)
        self._metrics["queue_depth"] = len(self._queue)
        return await self._execute_next()

    async def _execute_next(self) -> Any:
        async with self._lock:
            if not self._queue:
                return None
            task = heapq.heappop(self._queue)
            wait = time.monotonic() - task.enqueued_at
            self._metrics["wait_times"].append(wait)
            try:
                return await asyncio.wait_for(task.coro, timeout=task.timeout_s)
            except asyncio.TimeoutError:
                raise GPUTimeoutError(f"Task {task.task_id} timed out after {task.timeout_s}s")

    async def _aging_loop(self):
        """Bump priority po 30s w kolejce (starvation prevention)."""
        while True:
            await asyncio.sleep(10)
            now = time.monotonic()
            for task in self._queue:
                if now - task.enqueued_at > 30 and task.priority > 1:
                    task.priority -= 1  # przesuń wyżej
            heapq.heapify(self._queue)

# Singleton dostępny globalnie
gpu_scheduler = GPUScheduler()

# Użycie:
# result = await gpu_scheduler.submit(
#     llm_client.generate(prompt), priority=2, task_id="llm_response"
# )
```

### 1.4 Test Cases

| ID | Input | Expected |
|----|-------|---------|
| GPU-T-01 | STT + VLM jednocześnie | STT wykonuje się pierwszy (priority 1 < 4) |
| GPU-T-02 | 5 LLM requestów | Kolejka FIFO per priorytet (heapq stable sort: FIFO przy równym) |
| GPU-T-03 | Task > 60s | `GPUTimeoutError`, następny task pobierany |
| GPU-T-04 | Task w kolejce 35s | Priority bumped o 1 |

---

## 2. Circuit Breaker (LM Studio + MCP)

### 2.1 Stany

```
CLOSED ──(3 failures)──► OPEN ──(30s)──► HALF_OPEN ──(success)──► CLOSED
                                                     ──(failure)──► OPEN
```

### 2.2 Implementacja

```python
from enum import Enum
import time

class CBState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout_s: float = 30.0,
    ):
        self.name = name
        self._state = CBState.CLOSED
        self._failures = 0
        self._opened_at: float | None = None
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout_s

    @property
    def state(self) -> CBState:
        if self._state == CBState.OPEN:
            if time.monotonic() - self._opened_at >= self._recovery_timeout:
                self._state = CBState.HALF_OPEN
        return self._state

    async def call(self, coro, fallback=None):
        if self.state == CBState.OPEN:
            if fallback is not None:
                return fallback
            raise CircuitOpenError(f"Circuit '{self.name}' is OPEN")

        try:
            result = await coro
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        self._failures = 0
        self._state = CBState.CLOSED

    def _on_failure(self):
        self._failures += 1
        if self._failures >= self._failure_threshold:
            self._state = CBState.OPEN
            self._opened_at = time.monotonic()

    def to_db_dict(self) -> dict:
        """Persist do system_state table (przeżywa restart z TTL)."""
        return {
            "key": f"circuit_breaker_{self.name}",
            "value": self._state.value,
            "updated_at": int(time.time()),
        }

# Per-endpoint (nie globalny):
lm_studio_cb = CircuitBreaker("lm_studio", failure_threshold=3, recovery_timeout_s=30)
web_search_cb = CircuitBreaker("web_search", failure_threshold=5, recovery_timeout_s=60)
```

### 2.3 Klasyfikacja błędów

Wszystkie błędy liczą się do failure count: timeout, HTTP 5xx, `ConnectionError`, `asyncio.TimeoutError`. HTTP 4xx NIE liczy się (błąd klienta, nie serwera).

### 2.4 Persistence (TTL)

```python
# Przy starcie backendu — przywróć state z DB:
async def restore_circuit_breakers(db: Connection, breakers: list[CircuitBreaker]):
    for cb in breakers:
        row = await db.fetchone(
            "SELECT value, updated_at FROM system_state WHERE key=? AND updated_at > ?",
            (f"circuit_breaker_{cb.name}", int(time.time()) - 300)  # TTL 5 min
        )
        if row and row["value"] == "open":
            cb._state = CBState.OPEN
            cb._opened_at = time.monotonic() - (time.time() - row["updated_at"])
```

### 2.5 Test Cases

| ID | Input | Expected |
|----|-------|---------|
| CB-T-01 | 3 failures | State → OPEN |
| CB-T-02 | State OPEN, request | `CircuitOpenError` |
| CB-T-03 | State OPEN, 30s elapsed | State → HALF_OPEN |
| CB-T-04 | State HALF_OPEN, success | State → CLOSED, failures = 0 |
| CB-T-05 | State HALF_OPEN, failure | State → OPEN |
| CB-T-06 | HTTP 404 response | failures count nie rośnie |

---

## 3. Session Watchdog (Hibernation Recovery)

### 3.1 Cel

Wykrywa hibernację systemu (brak ticków > 30s) i przeprowadza recovery sequence.

### 3.2 Implementacja

```python
import asyncio
import time

class SessionWatchdog:
    TICK_INTERVAL = 5.0    # co 5s
    HIBERNATE_THRESHOLD = 30.0  # brak ticku > 30s = hibernacja

    def __init__(self, services: "ServiceLocator"):
        self._services = services
        self._last_tick = time.monotonic()
        self._running = False

    async def start(self):
        self._running = True
        while self._running:
            now = time.monotonic()
            gap = now - self._last_tick
            self._last_tick = now

            if gap > self.HIBERNATE_THRESHOLD:
                await self._handle_hibernation(gap)

            await asyncio.sleep(self.TICK_INTERVAL)

    async def _handle_hibernation(self, gap_s: float):
        """Recovery sequence po hibernate."""
        # 1. Oznacz sesję
        await self._services.session_repo.set_health_state(
            "resumed_after_hibernate"
        )

        # 2. Reconnect WebSocket (sygnał do frontendu)
        await self._services.ws_manager.broadcast({
            "type": "system_state",
            "payload": {"state": "reconnecting"}
        })

        # 3. Ping LM Studio (5 prób co 5s)
        lm_ok = False
        for attempt in range(5):
            try:
                await self._services.llm_client.ping()
                lm_ok = True
                break
            except Exception:
                await asyncio.sleep(5)

        # 4. Reinit mikrofonu
        await self._services.audio_input.reinit()

        # 5. Emocja + TTS
        emotion = "confused"
        message = "O, wróciłeś! Właśnie się zresetowałem."
        if not lm_ok:
            emotion = "sad"
            message = "Wróciłem, ale LM Studio jest niedostępne."

        await self._services.tts.speak(message, emotion=emotion)
```

### 3.3 Crash Detection przy starcie

```python
async def detect_crash_on_startup(session_repo: SessionRepository) -> Optional[int]:
    """Zwraca crashed_session_id jeśli znaleziono."""
    crashed = await session_repo.find_unclosed()
    if crashed:
        await session_repo.set_health_state(crashed.id, "crashed")
        return crashed.id
    return None
```

### 3.4 Test Cases

| ID | Input | Expected |
|----|-------|---------|
| WD-T-01 | Brak ticku przez 35s | `_handle_hibernation()` wywołany |
| WD-T-02 | Normalny tick co 5s | Brak akcji |
| WD-T-03 | Startup z `ended_at IS NULL` | Session oznaczona jako `crashed` |
| WD-T-04 | Hibernate + LM Studio offline | Emocja `sad`, komunikat o braku LM |

---

## 4. Rate Limiter — Token Bucket (web_search)

### 4.1 Algorytm Token Bucket

```python
import time
import asyncio

class TokenBucketRateLimiter:
    """10 req/min = ~1 token / 6s. Burst: do 10 naraz."""

    def __init__(self, rate_per_minute: int = 10):
        self._rate = rate_per_minute
        self._capacity = rate_per_minute
        self._tokens = float(rate_per_minute)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        async with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False  # rate limited

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            self._capacity,
            self._tokens + elapsed * (self._rate / 60.0)
        )
        self._last_refill = now

web_search_limiter = TokenBucketRateLimiter(rate_per_minute=10)
```

### 4.2 Zachowanie na wyczerpanie

```python
async def rate_limited_web_search(query: str) -> list:
    if not await web_search_limiter.acquire():
        await emotion_service.set("disappointed")
        raise RateLimitedError("Nie mogę teraz szukać, spróbuję później.")
    return await _do_web_search(query)
```

### 4.3 Test Cases

| ID | Input | Expected |
|----|-------|---------|
| RL-T-01 | 10 calls w 1s | 10 sukcesów (burst) |
| RL-T-02 | 11. call w 1s | `RateLimitedError` |
| RL-T-03 | 10 calls, czekaj 60s, 10 calls | Wszystkie 20 sukces |

---

## 5. MCP Cache (SHA256 + TTL)

### 5.1 Generowanie klucza

```python
import hashlib
import json

def make_cache_key(tool_name: str, params: dict) -> str:
    """Kanonikalizacja: sorted keys, no whitespace, deterministic."""
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True)
    payload = f"{tool_name}:{canonical}"
    return hashlib.sha256(payload.encode()).hexdigest()

# Przykład:
# make_cache_key("web_search", {"query": "PoE2 build", "max_results": 5})
# → sha256("web_search:{"max_results":5,"query":"PoE2 build"}")
```

### 5.2 TTL per tool

| Tool | TTL (sekundy) | Uzasadnienie |
|------|--------------|--------------|
| `web_search` (game meta) | 86400 (24h) | Meta zmienia się rzadko |
| `web_search` (inne) | 3600 (1h) | Ogólna aktualność |
| `web_scraper` | 604800 (7 dni) | Strony rzadko się zmieniają |
| `get_current_time` | 0 (brak cache) | Zawsze aktualne |
| `calculator` | 0 | Deterministyczne, szybkie |
| `generate_document` | 0 | Zawsze nowy plik |
| `screen_capture` | 0 | Real-time |

### 5.3 Implementacja

```python
import asyncio
import time

class MCPCache:
    def __init__(self, repo: "MCPCacheRepository"):
        self._repo = repo
        self._locks: dict[str, asyncio.Lock] = {}

    async def get_or_fetch(
        self, tool_name: str, params: dict,
        fetch_fn, ttl_seconds: int
    ):
        if ttl_seconds == 0:
            return await fetch_fn()

        key = make_cache_key(tool_name, params)

        # Cache stampede prevention — per-key lock
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        async with self._locks[key]:
            # Check cache
            cached = await self._repo.get(key)
            if cached and (time.time() - cached.created_at) < ttl_seconds:
                await self._repo.increment_hit_count(key)
                return cached.output_json

            # Fetch fresh
            result = await fetch_fn()
            await self._repo.upsert(key, tool_name, params, result, ttl_seconds)
            return result

    async def invalidate_all(self):
        await self._repo.delete_all()
```

### 5.4 Cleanup

```python
async def cleanup_expired(repo: MCPCacheRepository):
    """Uruchamiane przy starcie i co 6h."""
    expired_keys = await repo.find_expired(time.time())
    for key in expired_keys:
        await repo.delete(key)
```

### 5.5 Test Cases

| ID | Input | Expected |
|----|-------|---------|
| CACHE-T-01 | web_search("PoE2") → web_search("PoE2") < 24h | 2. call = cache hit, brak network |
| CACHE-T-02 | web_search("PoE2") → invalidate_all → web_search("PoE2") | 3. call = fresh fetch |
| CACHE-T-03 | 2 równoległe identyczne requesty | Lock: 2. czeka na 1., zwraca ten sam wynik |
| CACHE-T-04 | Cache entry starszy niż TTL | Treated as miss |

---

## 6. Observer Loop

### 6.1 Główna pętla

```python
import asyncio
import time
from collections import deque

class ObserverLoop:
    def __init__(self, services: "ServiceLocator"):
        self._services = services
        self._running = False
        self._paused = False
        self._last_hashes: deque[str] = deque(maxlen=3)  # deduplikacja

    async def start(self, interval_s: int):
        self._running = True
        while self._running:
            await asyncio.sleep(interval_s)
            if self._paused or not self._running:
                continue
            await self._run_cycle()

    async def _run_cycle(self):
        # Skip warunki
        if await self._services.audio_input.is_ptt_active():
            return
        if await self._services.system_state.get("sleep_mode"):
            return

        frame = await self._capture()
        if frame is None:
            return

        # Scene change detection (dHash)
        new_hash = compute_dhash(frame)
        if list(self._last_hashes).count(new_hash) >= 3:
            return  # statyczna scena × 3
        self._last_hashes.append(new_hash)

        # VLM + opcjonalnie OCR — backpressure: timeout 10s
        try:
            scene = await asyncio.wait_for(
                self._services.vlm.describe(frame), timeout=10.0
            )
        except asyncio.TimeoutError:
            return  # skip cycle, nie kolejkuj

        comment = await self._services.llm.generate_observer_comment(scene)
        if comment is None or comment.strip() == "[SKIP]":
            return

        await self._services.tts.speak(comment.text, emotion=comment.emotion)
        await self._services.message_repo.save_observer_message(comment.text, comment.emotion)

    async def pause(self):
        self._paused = True

    async def resume(self):
        await asyncio.sleep(2)  # grace period
        self._paused = False

    def stop(self):
        self._running = False

    async def _capture(self):
        try:
            return await self._services.screen_capture.capture()
        except Exception:
            return None
```

### 6.2 Test Cases

| ID | Scenario | Expected |
|----|----------|---------|
| OBS-T-01 | PTT aktywny w trakcie cycle | Skip cycle |
| OBS-T-02 | Identyczny scene_hash × 3 z rzędu | Skip cycle |
| OBS-T-03 | VLM timeout 11s | Skip cycle (nie crash) |
| OBS-T-04 | LLM zwraca "[SKIP]" | Brak TTS |

---

## 7. Scene Change Detection (dHash)

```python
import numpy as np
from PIL import Image

def compute_dhash(frame: np.ndarray, hash_size: int = 8) -> str:
    """Difference hash — szybki perceptual hash."""
    img = Image.fromarray(frame).convert("L")  # grayscale
    img = img.resize((hash_size + 1, hash_size), Image.LANCZOS)
    pixels = np.array(img)
    diff = pixels[:, 1:] > pixels[:, :-1]  # różnica sąsiednich pikseli
    return "".join("1" if b else "0" for b in diff.flatten())

def hamming_distance(h1: str, h2: str) -> int:
    return sum(c1 != c2 for c1, c2 in zip(h1, h2))

SCENE_CHANGE_THRESHOLD = 8  # Hamming distance > 8 = zmiana sceny
```

---

## 8. Audio Duck

```python
# Backend: przy wykryciu PTT → wyślij event do frontendu
async def handle_ptt_start(ws_manager: WebSocketManager, tts_player: TTSPlayer):
    tts_player.pause()  # zatrzymaj bieżące audio
    await ws_manager.broadcast({
        "type": "audio_duck",
        "payload": {"target_volume": 0.0, "ramp_ms": 200}
    })

async def handle_ptt_end(ws_manager: WebSocketManager, tts_player: TTSPlayer):
    # Nie wznawiaj observer TTS — priorytet user interaction
    await ws_manager.broadcast({
        "type": "audio_duck",
        "payload": {"target_volume": 1.0, "ramp_ms": 100}
    })
```

Frontend (Web Audio API): `GainNode.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.2)`.

---

## 9. Streaming Response Pipeline

```
LLM stream (token-by-token, OpenAI format)
        │
        ▼
TokenBuffer (akumuluj)
        │
        ▼ (przy wykryciu [.!?] + whitespace lub max 80 tokenów)
Sentence splitter
        │
        ▼
Emotion tag parser (parse_emotion_tag — tylko pierwsza zdanie)
        │
        ▼
TTS queue (per-sentence)
        │
        ▼
Audio chunks → WebSocket → Frontend AudioPlayer
```

### 9.1 Implementacja

```python
import re

SENTENCE_ENDINGS = re.compile(r"([.!?…])\s+")

async def stream_to_tts(
    token_stream, tts: "TTSEngine", ws: "WebSocketManager"
):
    buffer = ""
    first_sentence = True

    async for token in token_stream:
        buffer += token
        matches = list(SENTENCE_ENDINGS.finditer(buffer))
        if matches:
            last_match = matches[-1]
            sentence = buffer[:last_match.end()]
            buffer = buffer[last_match.end():]

            # Emocja tylko z pierwszego zdania
            if first_sentence:
                emotion, sentence = parse_emotion_tag(sentence)
                await ws.broadcast({"type": "emotion",
                                    "payload": {"emotion": emotion}})
                first_sentence = False

            # Generuj TTS asynchronicznie (pipeline)
            asyncio.create_task(
                tts.speak_and_stream(sentence, ws)
            )

    # Reszta bufforu po zakończeniu stream
    if buffer.strip():
        asyncio.create_task(tts.speak_and_stream(buffer.strip(), ws))
```

**Target:** first sentence latency < 1.5s od PTT release.

---

## 10. ChromaDB Rotation FIFO

```python
async def rotate_if_needed(
    chroma_conv: "ChromaCollection",
    msg_repo: "MessageRepository",
    limit: int = 10_000,
    batch_size: int = 100,
):
    count = chroma_conv.count()
    if count < limit:
        return

    # Znajdź najstarsze embedding IDs
    oldest = await msg_repo.find_oldest_embeddings(
        limit=batch_size,
        where={"include_in_semantic_memory": True, "archived": False}
    )
    embedding_ids = [r.chroma_embedding_id for r in oldest if r.chroma_embedding_id]

    if not embedding_ids:
        return

    # Atomic: chroma delete → SQLite null (retry 3x jeśli SQLite fail)
    chroma_conv.delete(ids=embedding_ids)
    for attempt in range(3):
        try:
            await msg_repo.nullify_embedding_ids(embedding_ids)
            break
        except Exception:
            if attempt == 2:
                raise  # log critical
            await asyncio.sleep(0.5)
```

---

## 11. Daily Meta Check

```python
async def run_daily_meta_check(
    player_profile: PlayerProfile,
    web_search: "MCPWebSearch",
    knowledge_repo: "KnowledgeRepository",
    daily_check_repo: "DailyCheckRepository",
    last_check_threshold_hours: int = 24,
):
    if not should_run(daily_check_repo, last_check_threshold_hours):
        return

    for game_id, game_data in player_profile.games.items():
        query = f"{game_data['name']} meta build patch {game_id} 2026"
        try:
            results = await web_search.search(query, max_results=5)
            content = format_meta_results(results, game_data)
            path = f"knowledge/{game_id}/daily_{date.today()}.md"
            await knowledge_repo.write(path, content)
            await daily_check_repo.record(game_id, len(results))
        except Exception as e:
            await daily_check_repo.record(game_id, 0, error=str(e))

def should_run(repo: "DailyCheckRepository", hours: int) -> bool:
    last = repo.last_check_time()
    if last is None:
        return True
    return (time.time() - last) > hours * 3600
```

---

## 12. Auto-Archive Logs

```python
import py7zr
from pathlib import Path
from datetime import datetime, timedelta

async def archive_old_logs(content_root: Path, max_age_days: int = 30):
    logs_dir = content_root / "logs"
    archive_dir = content_root / "logs" / "archive"
    archive_dir.mkdir(exist_ok=True)

    cutoff = datetime.now() - timedelta(days=max_age_days)
    for log_file in logs_dir.glob("*.md"):
        if datetime.fromtimestamp(log_file.stat().st_mtime) < cutoff:
            archive_path = archive_dir / f"{log_file.stem}_{date.today()}.7z"
            with py7zr.SevenZipFile(archive_path, "w") as z:
                z.write(log_file, log_file.name)
            # Verify przed delete
            with py7zr.SevenZipFile(archive_path, "r") as z:
                names = z.getnames()
            if log_file.name in names:
                log_file.unlink()
```

---

*Dokument: DOK-08 ALGORITHMS_SPEC.md v1.0 — 2026-04-30*
*Następny: DOK-09 OBSERVER_SPEC.md*
