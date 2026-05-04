-- Initial schema — docs/DB_SCHEMA.md (SQLite). Wersja migracji: 1.

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
    scene_hash                 TEXT,
    include_in_semantic_memory BOOLEAN NOT NULL DEFAULT FALSE,
    chroma_embedding_id        TEXT,
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

CREATE VIEW latest_observer_context AS
SELECT content, emotion, created_at, session_id
FROM messages
WHERE source = 'observer';

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
    tool_call_id    INTEGER REFERENCES tool_calls(id),
    filename        TEXT    NOT NULL,
    format          TEXT    NOT NULL CHECK(format IN ('md','html')),
    topic           TEXT,
    file_path       TEXT,
    file_size_bytes INTEGER,
    created_at      INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE INDEX idx_documents_session
    ON generated_documents(session_id, created_at DESC);

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
    cache_key     TEXT    NOT NULL CHECK(length(cache_key) = 64),
    response_json TEXT    NOT NULL,
    ttl_seconds   INTEGER NOT NULL CHECK(ttl_seconds > 0),
    hit_count     INTEGER NOT NULL DEFAULT 0,
    created_at    INTEGER NOT NULL DEFAULT (unixepoch()),
    UNIQUE(cache_key)
);

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
