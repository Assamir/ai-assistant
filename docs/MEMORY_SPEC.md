# DOK-11: MEMORY_SPEC.md — Specyfikacja Pamięci i Persystencji

> **Status:** v1.0 — 2026-04-30
> **Materiały źródłowe:** DB_SCHEMA.md (cały), PRD_02_FUNCTIONAL.md (§6 Pamięć), PRD_06_IMPLEMENTATION.md

---

## 1. Repository Pattern — Interfejsy

```python
from abc import ABC, abstractmethod
from typing import Optional, AsyncIterator

class BaseRepository(ABC):
    def __init__(self, db: "AsyncConnection"):
        self._db = db

    async def execute(self, sql: str, params: tuple = ()) -> None:
        await self._db.execute(sql, params)

    async def fetchone(self, sql: str, params: tuple = ()) -> Optional[dict]:
        return await self._db.fetchone(sql, params)

    async def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        return await self._db.fetchall(sql, params)
```

### 1.1 SessionRepository

```python
class SessionRepository(BaseRepository):
    async def create(self) -> int: ...                              # INSERT, returns id
    async def close(self, session_id: int) -> None: ...            # SET ended_at
    async def find_unclosed(self) -> Optional[Session]: ...        # crash detection
    async def set_health_state(self, sid: int, state: str): ...
    async def get_active(self) -> Optional[Session]: ...
    async def find_by_id(self, sid: int) -> Optional[Session]: ...
    async def list_recent(self, limit: int = 10) -> list[Session]: ...
```

### 1.2 MessageRepository

```python
class MessageRepository(BaseRepository):
    async def save(self, msg: Message) -> int: ...
    async def get_recent(self, session_id: int, limit: int = 20,
                         exclude_observer: bool = False) -> list[Message]: ...
    async def get_observer_recent(self, session_id: int, limit: int = 2) -> list[Message]: ...
    async def update_embedding_id(self, msg_id: int, chroma_id: str): ...
    async def find_oldest_embeddings(self, limit: int) -> list[Message]: ...
    async def nullify_embedding_ids(self, ids: list[str]): ...
    async def mark_archived(self, older_than_days: int): ...
    async def save_observer_message(self, content: str, emotion: str,
                                    scene_hash: str, session_id: int) -> int: ...
```

### 1.3 MCPCacheRepository

```python
class MCPCacheRepository(BaseRepository):
    async def get(self, cache_key: str) -> Optional[CacheEntry]: ...
    async def upsert(self, key: str, tool_name: str, params: dict,
                     output: Any, ttl_s: int): ...
    async def increment_hit_count(self, key: str): ...
    async def find_expired(self, now: float) -> list[str]: ...   # keys
    async def delete(self, key: str): ...
    async def delete_all(self): ...
```

### 1.4 PlayerProfileRepository

```python
class PlayerProfileRepository:
    """YAML jako source of truth. SQLite = read-only snapshots."""
    def __init__(self, profile_path: Path, db: AsyncConnection):
        self._path = profile_path
        self._db = db

    def load(self) -> PlayerProfile: ...
    def save(self, profile: PlayerProfile): ...
    async def set_active_character(self, game_id: str, char_name: str): ...
    async def insert_snapshot(self, session_id: int, game_id: str,
                               trigger: str): ...
    async def get_active_snapshot(self, game_id: str) -> Optional[dict]: ...
    async def archive_season(self, game_id: str, league_name: str): ...
```

### 1.5 Pozostałe repozytoria (interfejs skrócony)

| Repository | Kluczowe metody |
|-----------|----------------|
| `ToolCallRepository` | `create`, `update_result`, `get_by_message` |
| `DocumentRepository` | `save`, `list_recent`, `find_by_filename` |
| `GameDetectionRepository` | `start`, `stop`, `find_active`, `list_recent` |
| `HealthEventRepository` | `record`, `find_recent`, `find_by_type` |
| `SystemStateRepository` | `get(key)`, `set(key, value)`, `get_all` |
| `DailyCheckRepository` | `record`, `last_check_time`, `find_recent` |

---

## 2. Storage Backend Abstraction

```python
from abc import ABC

class StorageBackend(ABC):
    @abstractmethod
    async def connect(self) -> "AsyncConnection": ...

    @abstractmethod
    async def close(self): ...

class SQLiteBackend(StorageBackend):
    def __init__(self, path: str):
        self._path = path

    async def connect(self):
        import aiosqlite
        conn = await aiosqlite.connect(self._path)
        conn.row_factory = aiosqlite.Row
        for pragma in PRAGMAS:
            await conn.execute(pragma)
        return conn

# Future implementations (nie w MVP):
# class PostgresBackend(StorageBackend): ...
# class GcpFirestoreBackend(StorageBackend): ...
```

**Migration path:** swap backend = zmiana `storage.backend: sqlite|postgres` w config + restart. Repository interfejsy są niezależne od backendu.

---

## 3. Message Save Pipeline

```
User mówi
        │
        ▼
STT → transcription (string)
        │
        ▼
CommandMatcher (brak komendy) → LLM → response
        │
        ▼
MessageRepository.save(user_message)
        │
        ├─ source='user' → include_in_semantic_memory = TRUE
        │
        ▼
ChromaDB.conversations.add(embedding, metadata)
        │
        ▼
MessageRepository.update_embedding_id(chroma_id)
        │
        ▼
(Analogicznie dla assistant response gdy len > 100 znaków)
```

### 3.1 Decision matrix: `include_in_semantic_memory`

| `source` | `length` | `include_in_semantic_memory` |
|---------|---------|------------------------------|
| `user` | dowolna | TRUE |
| `assistant` | > 100 znaków | TRUE |
| `assistant` | ≤ 100 znaków | FALSE |
| `observer` | dowolna | FALSE |
| `system` | dowolna | FALSE |

### 3.2 Embedding generation

```python
from sentence_transformers import SentenceTransformer

embedder = SentenceTransformer(
    "paraphrase-multilingual-MiniLM-L12-v2",
    cache_folder=str(content_root / "models" / "embeddings"),
    device="cuda",
)

async def embed_and_store(msg: Message, chroma: ChromaCollection):
    loop = asyncio.get_event_loop()
    embedding = await loop.run_in_executor(
        None, embedder.encode, msg.content
    )
    chroma.add(
        ids=[f"msg_{msg.id}"],
        embeddings=[embedding.tolist()],
        documents=[msg.content],
        metadatas=[{
            "source": msg.source,
            "session_id": msg.session_id,
            "created_at": msg.created_at,
            "emotion": msg.emotion or "",
        }]
    )
    return f"msg_{msg.id}"
```

---

## 4. Semantic Recall Algorithm

```python
async def semantic_recall(
    query: str,
    chroma_conv: ChromaCollection,
    chroma_know: ChromaCollection,
    game_id: Optional[str] = None,
    k_conv: int = 3,
    k_know: int = 2,
) -> str:
    loop = asyncio.get_event_loop()
    query_emb = await loop.run_in_executor(None, embedder.encode, query)

    # Step 1: konwersacje
    conv_results = chroma_conv.query(
        query_embeddings=[query_emb.tolist()],
        n_results=k_conv,
        where={"source": {"$in": ["user", "assistant"]}},
    )

    # Step 2: knowledge base (z filtrem gry)
    know_where = {"game_id": game_id} if game_id else {}
    know_results = chroma_know.query(
        query_embeddings=[query_emb.tolist()],
        n_results=k_know,
        where=know_where if know_where else None,
    )

    # Step 3: deduplikacja (cosine > 0.95)
    all_docs = list(zip(
        conv_results["documents"][0] + know_results["documents"][0],
        conv_results["metadatas"][0] + know_results["metadatas"][0],
        conv_results.get("distances", [[]])[0] + know_results.get("distances", [[]])[0],
    ))
    unique = deduplicate_by_similarity(all_docs, threshold=0.95)

    # Step 4: format dla promptu
    return format_recall(unique)

def format_recall(docs: list) -> str:
    if not docs:
        return ""
    lines = ["[Wcześniejsze wspomnienia]"]
    for doc, meta, _ in docs:
        age = _human_age(meta.get("created_at", 0))
        lines.append(f"- {age}: \"{doc[:200]}\"")
    return "\n".join(lines)
```

---

## 5. Knowledge Base Ingestion

### 5.1 Folder watcher

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class KnowledgeWatcher(FileSystemEventHandler):
    def __init__(self, ingester: "KnowledgeIngester"):
        self._ingester = ingester

    def on_modified(self, event):
        if event.src_path.endswith(".md"):
            asyncio.run_coroutine_threadsafe(
                self._ingester.ingest_file(Path(event.src_path)),
                loop=asyncio.get_event_loop(),
            )

knowledge_dir = content_root / "knowledge"
observer = Observer()
observer.schedule(KnowledgeWatcher(ingester), str(knowledge_dir), recursive=True)
observer.start()
```

### 5.2 Chunking strategia

```python
def chunk_markdown(text: str, max_tokens: int = 500, overlap: int = 50) -> list[str]:
    """Split po nagłówkach (## lub ###), potem po tokenach jeśli za długi."""
    sections = re.split(r"(?=^#{1,3} )", text, flags=re.MULTILINE)
    chunks = []
    for section in sections:
        tokens = len(section.split())  # przybliżone tokeny
        if tokens <= max_tokens:
            chunks.append(section.strip())
        else:
            # Dalszy split po tokenach z overlapping
            words = section.split()
            for i in range(0, len(words), max_tokens - overlap):
                chunk = " ".join(words[i:i + max_tokens])
                chunks.append(chunk)
    return [c for c in chunks if len(c) > 50]
```

### 5.3 Re-ingestion (zmiana pliku)

```python
async def ingest_file(self, path: Path):
    source_file = str(path.relative_to(content_root))
    # Usuń stare chunki z tego pliku
    self._chroma.delete(where={"source_file": source_file})
    # Dodaj nowe
    content = path.read_text(encoding="utf-8")
    chunks = chunk_markdown(content)
    game_id = _extract_game_id(path)  # z ścieżki np. knowledge/poe2/...
    for i, chunk in enumerate(chunks):
        emb = embedder.encode(chunk)
        self._chroma.add(
            ids=[f"{source_file}_{i}"],
            embeddings=[emb.tolist()],
            documents=[chunk],
            metadatas=[{
                "source_file": source_file,
                "game_id": game_id or "",
                "file_updated_at": int(path.stat().st_mtime),
            }]
        )
```

---

## 6. ChromaDB Rotation FIFO

Z DOK-08 ALGORITHMS_SPEC.md sekcja 10.

- Limit: 10 000 embeddings w kolekcji `conversations`
- Batch: 100 najstarszych
- Trigger: po każdym INSERT (count check) — lub batch co 1000 insertów
- Kolekcja `knowledge_base`: bez limitu (pliki `.md` generowane przez użytkownika/daily check)

---

## 7. Player Profile Management

### 7.1 YAML jako source of truth

```yaml
# data/player_profile.yaml
games:
  poe2:
    active_character: "SparkyBoy"
    league: "Settlers of Kalguur S2"
    characters:
      - name: "SparkyBoy"
        class: "Deadeye"
        build: "Lightning Arrow"
        level: 87
        build_url: "https://maxroll.gg/poe2/la-deadeye"
        notes: "Potrzebuje lepszego łuku T1"
      - name: "TankMaster"
        class: "Warrior"
        build: "Molten Strike Juggernaut"
        level: 42
    last_meta_check: "2026-04-25"
  stellaris:
    active_empire: "Zjednoczona Federacja"
    game_version: "3.14"
```

### 7.2 Update flow

```python
async def change_active_character(game_id: str, char_name: str,
                                   session_id: int):
    profile = player_repo.load()
    game = profile.games.get(game_id)
    if not game:
        raise ValueError(f"Game '{game_id}' not in profile")
    char_names = [c.name.lower() for c in game.characters]
    # Fuzzy match (STT może zniekształcić imię)
    match = best_match(char_name.lower(), char_names, threshold=0.8)
    if not match:
        raise ValueError(f"Character '{char_name}' not found")
    game.active_character = match
    player_repo.save(profile)
    await player_repo.insert_snapshot(session_id, game_id, "character_change")
```

### 7.3 Snapshot triggers

| Trigger | Snapshot event | Kiedy |
|---------|----------------|-------|
| `session_start` | Każdy start backendu | Zawsze |
| `character_change` | Zmiana active_character | Po komendzie |
| `game_detected` | GameDetector potwierdził grę | Po detekcji |

---

## 8. Build Import z URL

```python
async def import_build_from_url(url: str, game_id: str, char_name: str):
    try:
        scraped = await web_scraper_tool.execute({"url": url}, ctx)
        # LLM wyciąga dane buildu z treści
        build_data = await llm.extract_build_info(scraped["content_markdown"])
        # Konwersacyjne potwierdzenie
        await tts.speak(
            f"Znalazłem build: {build_data['name']}. "
            f"Klasa: {build_data['class']}. Zapisać?", emotion="thinking"
        )
        # Czekaj na potwierdzenie (confirmation session)
        return build_data
    except Exception:
        await tts.speak(
            "Nie udało mi się załadować buildu z tego URL. "
            "Chcesz podać dane ręcznie?", emotion="confused"
        )
```

---

## 9. Auto-Archive Strategy

### 9.1 Sessions (messages)

```python
async def archive_old_messages(db: AsyncConnection, max_age_days: int = 90):
    cutoff = int(time.time()) - max_age_days * 86400
    await db.execute(
        "UPDATE messages SET archived=TRUE, archived_at=unixepoch() "
        "WHERE created_at < ? AND archived=FALSE",
        (cutoff,)
    )
```

Archiwizacja = oznaczenie `archived=TRUE`. Wiadomości NIE są fizycznie usuwane w MVP.

### 9.2 Logs

Z DOK-08 ALGORITHMS_SPEC.md sekcja 12 — `archive_old_logs()`.

---

## 10. Backup/Restore

```python
import zipfile
from datetime import date

async def create_backup(content_root: Path) -> Path:
    backup_dir = content_root / "backups"
    backup_dir.mkdir(exist_ok=True)
    filename = f"assystent_backup_{date.today().isoformat()}.zip"
    backup_path = backup_dir / filename

    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in content_root.rglob("*"):
            if file.is_file() and not _should_exclude(file, content_root):
                zf.write(file, file.relative_to(content_root))

    return backup_path

def _should_exclude(file: Path, root: Path) -> bool:
    excluded = {root / "backups", root / "data" / "memory"}
    return any(str(file).startswith(str(ex)) for ex in excluded)
```

ChromaDB binary indexes (`data/memory/*.bin`) są wykluczone — mogą być zregenerowane z `conversations.db`.

---

## 11. Season Reset Detection

```python
SEASON_KEYWORDS = {"new league", "new season", "season reset", "league start", "nowa liga"}

async def detect_season_reset(game_id: str, search_results: list[dict],
                               player_profile: PlayerProfile):
    current_league = player_profile.games[game_id].get("league", "")
    for result in search_results:
        text = (result.get("title", "") + " " + result.get("snippet", "")).lower()
        if any(kw in text for kw in SEASON_KEYWORDS):
            # Zapytaj użytkownika
            await tts.speak(
                f"Wygląda na nowy sezon w {game_id}. Reset profilu?",
                emotion="excited"
            )
            # Confirmation session (30s timeout)
            return True
    return False

async def archive_season(game_id: str, league: str, player_repo: PlayerProfileRepository):
    profile = player_repo.load()
    archive_data = {
        "game_id": game_id,
        "league": league,
        "archived_at": date.today().isoformat(),
        "characters": profile.games[game_id].get("characters", []),
    }
    archive_path = content_root / "data" / "archive" / f"{game_id}_{league}.yaml"
    archive_path.parent.mkdir(exist_ok=True)
    yaml.dump(archive_data, archive_path.open("w"), allow_unicode=True)
    # Reset characters w profilu
    profile.games[game_id]["characters"] = []
    profile.games[game_id]["active_character"] = None
    player_repo.save(profile)
```

---

## 12. Schema Migrations

```python
from pathlib import Path

class MigrationRunner:
    MIGRATIONS_DIR = Path("backend/db/migrations")

    async def up(self, db: AsyncConnection):
        await db.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL DEFAULT (unixepoch()))"
        )
        applied = {r["version"] for r in await db.fetchall("SELECT version FROM schema_migrations")}

        for sql_file in sorted(self.MIGRATIONS_DIR.glob("*.sql")):
            version = int(sql_file.stem.split("_")[0])
            if version in applied:
                continue
            sql = sql_file.read_text(encoding="utf-8")
            await db.executescript(sql)
            await db.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
            await db.commit()

# Przykładowe pliki:
# backend/db/migrations/001_initial.sql  ← cały DDL z DB_SCHEMA.md
# backend/db/migrations/002_add_index.sql
```

---

## 13. Test Strategy

```python
# conftest.py
import pytest
import aiosqlite
import chromadb

@pytest.fixture
async def in_memory_db():
    async with aiosqlite.connect(":memory:") as db:
        db.row_factory = aiosqlite.Row
        await MigrationRunner().up(db)
        yield db

@pytest.fixture
def ephemeral_chroma():
    client = chromadb.EphemeralClient()
    conv = client.create_collection("conversations")
    know = client.create_collection("knowledge_base")
    yield {"conversations": conv, "knowledge_base": know}

@pytest.fixture
def sample_session(in_memory_db):
    # 20 wiadomości (10 user + 10 assistant)
    ...
```

---

## 14. Performance

| Operacja | Target | Index |
|---------|--------|-------|
| `get_recent(session_id, limit=20)` | < 10ms | `idx_messages_session_created` |
| `semantic_recall(query)` | < 200ms | ChromaDB HNSW index |
| `save(message)` | < 5ms | WAL mode |
| `find_unclosed()` | < 5ms | `idx_sessions_active` (partial) |

VACUUM: opcjonalnie co tydzień (off-peak), nie blokuje WAL.

---

*Dokument: DOK-11 MEMORY_SPEC.md v1.0 — 2026-04-30*
*Następny: DOK-12 FRONTEND_SPEC.md*
