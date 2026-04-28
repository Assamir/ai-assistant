# Schemat Bazy Danych — Assystent MVP

> **Status:** v1.0 — Finalna wersja po sesji analitycznej (4 rundy, 40 decyzji)
> **Data:** 2026-04-26
> **Powiązane dokumenty:** PRD_04_ARCHITECTURE.md, PRD_02_FUNCTIONAL.md

---

## Kluczowe Decyzje Projektowe

| # | Decyzja |
|---|---------|
| 1 | Jedna tabela `messages` z kolumną `source` (`user/assistant/observer/system`) + flaga `include_in_semantic_memory` |
| 2 | Granica sesji = start/stop backendu; `ended_at IS NULL` = sesja aktywna; crash recovery przy starcie |
| 3 | YAML jako source of truth profilu gracza; SQLite przechowuje snapshoty kontekstu do promptów |
| 4 | Cache MCP: jedna tabela z `ttl_seconds`; klucz = SHA256(tool_name + canonical_json(params)) |
| 5 | ChromaDB: dwie kolekcje (`conversations` limit 10k FIFO, `knowledge_base` bez limitu); model embeddingów: `paraphrase-multilingual-MiniLM-L12-v2` |
| 6 | Kontekst LLM: ostatnie 20 wiadomości non-observer + 5 semantic recall + 1-2 komentarze obserwatora osobno |
| 7 | Snapshoty profilu gracza tworzone przy: `session_start`, `character_change`, `game_detected` |
| 8 | Migracje: tabela `schema_migrations` + numerowane pliki SQL w `backend/db/migrations/` |
| 9 | PRAGMA: WAL mode, synchronous=NORMAL, foreign_keys=ON, cache 64MB, mmap 256MB |
| 10 | Testy: SQLite `:memory:` + ChromaDB `EphemeralClient()` — zero zewnętrznych procesów |

---

## SQLite — `conversations.db`

### PRAGMA (przy każdym połączeniu)

```python
PRAGMAS = [
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA foreign_keys = ON",
    "PRAGMA cache_size = -64000",    # 64 MB
    "PRAGMA temp_store = MEMORY",
    "PRAGMA mmap_size = 268435456",  # 256 MB
]
```

### DDL — Pełny Schemat

```sql
-- ============================================================
-- MIGRACJE
-- ============================================================
CREATE TABLE schema_migrations (
    version     INTEGER PRIMARY KEY,
    applied_at  INTEGER NOT NULL DEFAULT (unixepoch())
);

-- ============================================================
-- SESJE
-- ============================================================
CREATE TABLE sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      INTEGER NOT NULL DEFAULT (unixepoch()),
    ended_at        INTEGER,
    game_detected   TEXT,
    health_state    TEXT NOT NULL DEFAULT 'healthy'
                    CHECK(health_state IN (
                        'healthy','degraded','minimal',
                        'crashed','resumed_after_hibernate'
                    ))
);

CREATE INDEX idx_sessions_active
    ON sessions(ended_at) WHERE ended_at IS NULL;

-- ============================================================
-- WIADOMOŚCI
-- ============================================================
CREATE TABLE messages (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id                 INTEGER NOT NULL REFERENCES sessions(id),
    source                     TEXT    NOT NULL
                               CHECK(source IN ('user','assistant','observer','system')),
    content                    TEXT    NOT NULL CHECK(length(content) > 0),
    emotion                    TEXT,
    confidence_score           REAL,
    scene_hash                 TEXT,    -- tylko source='observer': SHA256 opisu VLM (deduplikacja)
    include_in_semantic_memory BOOLEAN NOT NULL DEFAULT FALSE,
    chroma_embedding_id        TEXT,    -- klucz do kolekcji ChromaDB 'conversations'
    archived                   BOOLEAN NOT NULL DEFAULT FALSE,
    archived_at                INTEGER,
    created_at                 INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE INDEX idx_messages_session_created
    ON messages(session_id, created_at DESC);
CREATE INDEX idx_messages_source_session
    ON messages(source, session_id);
CREATE INDEX idx_messages_semantic
    ON messages(include_in_semantic_memory, archived);

-- Widok: ostatnie komentarze obserwatora do prompt buildera
CREATE VIEW latest_observer_context AS
SELECT content, emotion, created_at, session_id
FROM messages
WHERE source = 'observer'
ORDER BY created_at DESC;

-- FTS5: full-text search po treści wiadomości
CREATE VIRTUAL TABLE messages_fts
    USING fts5(content, content='messages', content_rowid='id');

CREATE TRIGGER messages_fts_insert AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (NEW.id, NEW.content);
END;
CREATE TRIGGER messages_fts_delete AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content)
    VALUES ('delete', OLD.id, OLD.content);
END;

-- ============================================================
-- WYWOŁANIA NARZĘDZI MCP
-- ============================================================
CREATE TABLE tool_calls (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id    INTEGER NOT NULL REFERENCES messages(id),
    turn_sequence INTEGER NOT NULL CHECK(turn_sequence BETWEEN 1 AND 5),
    tool_name     TEXT    NOT NULL,
    input_json    TEXT    NOT NULL,
    output_json   TEXT,
    duration_ms   INTEGER,
    success       BOOLEAN NOT NULL DEFAULT FALSE,
    error_message TEXT,
    created_at    INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE INDEX idx_tool_calls_message
    ON tool_calls(message_id, turn_sequence);

-- ============================================================
-- WYGENEROWANE DOKUMENTY
-- ============================================================
CREATE TABLE generated_documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES sessions(id),
    tool_call_id    INTEGER REFERENCES tool_calls(id),  -- nullable: komenda systemowa
    filename        TEXT    NOT NULL,
    format          TEXT    NOT NULL CHECK(format IN ('md','html')),
    topic           TEXT,
    file_path       TEXT,   -- NULL jeśli plik fizycznie usunięty
    file_size_bytes INTEGER,
    created_at      INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE INDEX idx_documents_session
    ON generated_documents(session_id, created_at DESC);

-- Log plików do fizycznego usunięcia przez job cleanup
CREATE TABLE deleted_files_log (
    file_path  TEXT    NOT NULL,
    deleted_at INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE TRIGGER trg_document_delete AFTER DELETE ON generated_documents
WHEN OLD.file_path IS NOT NULL BEGIN
    INSERT INTO deleted_files_log(file_path) VALUES (OLD.file_path);
END;

-- ============================================================
-- CACHE MCP
-- ============================================================
CREATE TABLE mcp_cache (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_name     TEXT    NOT NULL,
    cache_key     TEXT    NOT NULL CHECK(length(cache_key) = 64),  -- SHA256 hex
    response_json TEXT    NOT NULL,
    ttl_seconds   INTEGER NOT NULL CHECK(ttl_seconds > 0),
    hit_count     INTEGER NOT NULL DEFAULT 0,
    created_at    INTEGER NOT NULL DEFAULT (unixepoch()),
    UNIQUE(cache_key)
);

-- TTL domyślne per tool:
--   web_search:       86400   (24h)
--   web_scraper:      604800  (7 dni)
--   get_current_time: 0       (brak cache)
--   calculator:       0       (brak cache)

CREATE INDEX idx_mcp_cache_lookup
    ON mcp_cache(tool_name, cache_key);
CREATE INDEX idx_mcp_cache_expiry
    ON mcp_cache(created_at, ttl_seconds);

-- ============================================================
-- PROFIL GRACZA — SNAPSHOTY KONTEKSTU
-- ============================================================
CREATE TABLE player_context_snapshots (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       INTEGER NOT NULL REFERENCES sessions(id),
    game             TEXT    NOT NULL,
    active_character TEXT    NOT NULL,
    character_class  TEXT,
    build_name       TEXT,
    build_url        TEXT,
    league           TEXT,
    trigger          TEXT    NOT NULL
                     CHECK(trigger IN ('session_start','character_change','game_detected')),
    captured_at      INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE INDEX idx_snapshots_game
    ON player_context_snapshots(game, captured_at DESC);

-- ============================================================
-- ARCHIWUM PROFILI — RESET SEZONOWY
-- ============================================================
CREATE TABLE player_profile_archives (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    game          TEXT    NOT NULL,
    season        TEXT    NOT NULL,
    archive_date  INTEGER NOT NULL DEFAULT (unixepoch()),
    yaml_snapshot TEXT    NOT NULL,
    reason        TEXT    NOT NULL
                  CHECK(reason IN ('season_reset','manual','backup'))
);

-- ============================================================
-- WYKRYTE GRY W SESJI
-- ============================================================
CREATE TABLE game_detections (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       INTEGER NOT NULL REFERENCES sessions(id),
    game             TEXT    NOT NULL,
    process_name     TEXT,
    detection_method TEXT    NOT NULL
                     CHECK(detection_method IN ('process','vlm','manual')),
    started_at       INTEGER NOT NULL DEFAULT (unixepoch()),
    ended_at         INTEGER
);

CREATE INDEX idx_game_detections_session
    ON game_detections(session_id, started_at);

-- ============================================================
-- DAILY META CHECK
-- ============================================================
CREATE TABLE daily_checks (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    game                 TEXT    NOT NULL,
    checked_at           INTEGER NOT NULL DEFAULT (unixepoch()),
    result_summary       TEXT,
    knowledge_file_path  TEXT,
    has_changes          BOOLEAN NOT NULL DEFAULT FALSE,
    user_notified        BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_daily_checks_game
    ON daily_checks(game, checked_at DESC);

-- ============================================================
-- ZDARZENIA ZDROWIA SYSTEMU
-- ============================================================
-- Retention: 7 dni. Cleanup przy starcie:
-- DELETE FROM health_events WHERE created_at < unixepoch() - 604800;
CREATE TABLE health_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    component  TEXT    NOT NULL,
    event_type TEXT    NOT NULL,
    details    TEXT,
    created_at INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE INDEX idx_health_events_created
    ON health_events(created_at DESC);

-- ============================================================
-- STAN SYSTEMU (key-value)
-- ============================================================
CREATE TABLE system_state (
    key        TEXT    PRIMARY KEY,
    value      TEXT    NOT NULL,
    updated_at INTEGER NOT NULL DEFAULT (unixepoch())
);

INSERT INTO system_state(key, value) VALUES
    ('circuit_breaker_state',     'CLOSED'),
    ('circuit_breaker_failures',  '0'),
    ('circuit_breaker_last_fail', '0'),
    ('audio_mode',                'ptt'),
    ('silent_mode',               'FALSE'),
    ('proactivity_level',         'moderate'),
    ('observer_interval_seconds', '10'),
    ('current_persona',           'default'),
    ('active_session_id',         'NULL'),
    ('last_chroma_rotation',      '0');
```

### Cleanup przy starcie backendu

```python
def startup_cleanup(conn):
    conn.executescript("""
        -- Zamknij sesje z poprzednich crashy
        UPDATE sessions
        SET ended_at = unixepoch(), health_state = 'crashed'
        WHERE ended_at IS NULL
          AND id != (SELECT MAX(id) FROM sessions);

        -- Wyczyść stary log plików (>24h)
        DELETE FROM deleted_files_log
        WHERE deleted_at < unixepoch() - 86400;

        -- Wyczyść stare health_events (>7 dni)
        DELETE FROM health_events
        WHERE created_at < unixepoch() - 604800;

        -- Wyczyść wygasły cache MCP
        DELETE FROM mcp_cache
        WHERE created_at + ttl_seconds < unixepoch();

        -- Zresetuj silent_mode
        UPDATE system_state SET value = 'FALSE', updated_at = unixepoch()
        WHERE key = 'silent_mode';
    """)
```

---

## ChromaDB — Konfiguracja

### Inicjalizacja kolekcji

```python
import chromadb
from chromadb.utils import embedding_functions

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CHROMA_PATH     = r"c:\ai\asystent\data\memory"
CONV_LIMIT      = 10_000

embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=EMBEDDING_MODEL
)

client = chromadb.PersistentClient(path=CHROMA_PATH)

conversations = client.get_or_create_collection(
    name="conversations",
    embedding_function=embedding_fn,
    metadata={"hnsw:space": "cosine"}
)

knowledge_base = client.get_or_create_collection(
    name="knowledge_base",
    embedding_function=embedding_fn,
    metadata={"hnsw:space": "cosine"}
)
```

### Metadane dokumentów

**Kolekcja `conversations`:**
```python
{
    "message_id":  int,
    "session_id":  int,
    "game":        str | None,
    "emotion":     str | None,
    "source":      "user" | "assistant",
    "created_at":  int    # unixepoch
}
```

**Kolekcja `knowledge_base`:**
```python
{
    "source_file":     str,   # np. "poe2/season2_meta.md"
    "game":            str,
    "section_title":   str,
    "chunk_index":     int,
    "type":            "daily_check" | "manual" | "wiki",
    "file_updated_at": int
}
```

### Semantic Recall — Prompt Builder

```python
def semantic_recall(query: str, game: str | None = None, k_conv=3, k_know=2):
    conv_results = conversations.query(
        query_texts=[query],
        n_results=k_conv,
        where={"source": {"$in": ["user", "assistant"]}}
    )
    know_filter = {"game": game} if game else {}
    know_results = knowledge_base.query(
        query_texts=[query],
        n_results=k_know,
        where=know_filter if know_filter else None
    )
    return conv_results, know_results
```

### Rotacja FIFO

```python
def rotate_if_needed(collection, sqlite_conn, limit=CONV_LIMIT, batch=100):
    if collection.count() < limit:
        return
    oldest = sqlite_conn.execute(
        "SELECT chroma_embedding_id FROM messages "
        "WHERE include_in_semantic_memory = 1 "
        "  AND archived = 0 "
        "  AND chroma_embedding_id IS NOT NULL "
        "ORDER BY created_at ASC LIMIT ?", (batch,)
    ).fetchall()
    ids = [row[0] for row in oldest]
    if not ids:
        return
    collection.delete(ids=ids)                          # 1. usuń z ChromaDB
    placeholders = ",".join("?" * len(ids))
    sqlite_conn.execute(                                # 2. wyzeruj referencję w SQLite
        f"UPDATE messages SET chroma_embedding_id = NULL "
        f"WHERE chroma_embedding_id IN ({placeholders})", ids
    )
    sqlite_conn.execute(
        "UPDATE system_state SET value = ?, updated_at = unixepoch() "
        "WHERE key = 'last_chroma_rotation'", (str(int(time.time())),)
    )
```

### Ingestion Knowledge Base (chunking)

```python
def ingest_knowledge_file(file_path: str, game: str, file_type: str = "manual"):
    text = Path(file_path).read_text(encoding="utf-8")
    chunks = split_markdown(text, max_tokens=500, overlap=50)  # własna funkcja
    knowledge_base.delete(where={"source_file": file_path})    # usuń stare chunki
    knowledge_base.add(
        documents=[c.text for c in chunks],
        metadatas=[{
            "source_file":     file_path,
            "game":            game,
            "section_title":   c.section_title,
            "chunk_index":     i,
            "type":            file_type,
            "file_updated_at": int(Path(file_path).stat().st_mtime)
        } for i, c in enumerate(chunks)],
        ids=[f"{file_path}::{i}" for i in range(len(chunks))]
    )
```

---

## Struktura plików `backend/db/`

```
backend/db/
├── connection.py              # setup połączenia, PRAGMA, migration runner
├── migrations/
│   ├── 001_initial.sql        # pełny schemat (tabele, indeksy, widoki, triggery)
│   └── 002_fts5.sql           # FTS5 — opcjonalne wyłączenie na słabszych maszynach
├── repositories/
│   ├── messages.py            # CRUD + semantic memory bridge
│   ├── sessions.py            # start/stop/crash recovery
│   ├── mcp_cache.py           # get/set/invalidate + SHA256 key
│   ├── tool_calls.py          # zapis wywołań per tura
│   ├── documents.py           # rejestr dokumentów + deleted_files_log
│   ├── player_snapshots.py    # snapshot przy zmianie kontekstu
│   ├── daily_checks.py        # tracking daily meta check
│   ├── game_detections.py     # historia gier w sesji
│   └── system_state.py        # key-value get/set
└── chromadb_client.py         # inicjalizacja kolekcji, recall, rotacja FIFO, ingestion
```

---

## Tabele — Podsumowanie

| Tabela | Typ | Cel |
|--------|-----|-----|
| `schema_migrations` | SQLite | Wersjonowanie schematu |
| `sessions` | SQLite | Granice sesji, stan zdrowia |
| `messages` | SQLite | Wszystkie wiadomości (user/assistant/observer/system) |
| `messages_fts` | SQLite FTS5 | Full-text search po treści |
| `tool_calls` | SQLite | Wywołania MCP tools per tura |
| `generated_documents` | SQLite | Rejestr wygenerowanych plików |
| `deleted_files_log` | SQLite | Kolejka do fizycznego usunięcia plików |
| `mcp_cache` | SQLite | Cache odpowiedzi MCP z TTL |
| `player_context_snapshots` | SQLite | Kontekst gracza do promptów |
| `player_profile_archives` | SQLite | Archiwa profili po resecie sezonu |
| `game_detections` | SQLite | Historia wykrytych gier w sesji |
| `daily_checks` | SQLite | Tracking daily meta check per gra |
| `health_events` | SQLite | Historia zdarzeń systemu (retention 7d) |
| `system_state` | SQLite | Key-value: tryby, circuit breaker, persona |
| `conversations` | ChromaDB | Embeddingi wiadomości (limit 10k, FIFO) |
| `knowledge_base` | ChromaDB | Chunki plików .md z `knowledge/` |

**Łącznie: 14 tabel SQLite + 1 widok + 3 triggery + 10 indeksów + 2 kolekcje ChromaDB**
