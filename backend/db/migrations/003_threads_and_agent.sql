-- Wątki konwersacji + zadania agentowe. Wersja migracji: 3.

-- ============================================================
-- WĄTKI KONWERSACJI
-- ============================================================
CREATE TABLE conversation_threads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK(status IN ('active','paused','closed')),
    topic_summary   TEXT,
    key_decisions   TEXT NOT NULL DEFAULT '[]',
    key_directions  TEXT NOT NULL DEFAULT '[]',
    message_count   INTEGER NOT NULL DEFAULT 0,
    created_at      INTEGER NOT NULL DEFAULT (unixepoch()),
    updated_at      INTEGER NOT NULL DEFAULT (unixepoch()),
    last_active_at  INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE INDEX idx_threads_status_last
    ON conversation_threads(status, last_active_at DESC);

CREATE TABLE thread_messages (
    message_id  INTEGER PRIMARY KEY REFERENCES messages(id),
    thread_id   INTEGER NOT NULL REFERENCES conversation_threads(id)
);

CREATE INDEX idx_thread_messages_thread
    ON thread_messages(thread_id);

-- ============================================================
-- ZADANIA AGENTOWE
-- ============================================================
CREATE TABLE agent_tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER REFERENCES sessions(id),
    thread_id       INTEGER REFERENCES conversation_threads(id),
    goal_text       TEXT NOT NULL,
    step_index      INTEGER NOT NULL DEFAULT 0,
    total_steps     INTEGER NOT NULL DEFAULT 1,
    description     TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','in_progress','done','failed','skipped')),
    result_summary  TEXT,
    quality_score   REAL,
    created_at      INTEGER NOT NULL DEFAULT (unixepoch()),
    updated_at      INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE INDEX idx_agent_tasks_session
    ON agent_tasks(session_id, created_at DESC);
CREATE INDEX idx_agent_tasks_thread
    ON agent_tasks(thread_id);

CREATE TABLE agent_notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER REFERENCES sessions(id),
    task_id     INTEGER REFERENCES agent_tasks(id),
    thread_id   INTEGER REFERENCES conversation_threads(id),
    content     TEXT NOT NULL,
    created_at  INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE INDEX idx_agent_notes_session
    ON agent_notes(session_id, created_at DESC);
CREATE INDEX idx_agent_notes_task
    ON agent_notes(task_id);

-- ============================================================
-- Rozszerzenie limitu turn_sequence (był 1..5, teraz 1..50)
-- SQLite nie obsługuje ALTER COLUMN CHECK — odtwarzamy tabelę.
-- ============================================================
CREATE TABLE tool_calls_v3 (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id    INTEGER NOT NULL REFERENCES messages(id),
    turn_sequence INTEGER NOT NULL CHECK(turn_sequence BETWEEN 1 AND 50),
    tool_name     TEXT    NOT NULL,
    input_json    TEXT    NOT NULL,
    output_json   TEXT,
    duration_ms   INTEGER,
    success       BOOLEAN NOT NULL DEFAULT FALSE,
    error_message TEXT,
    created_at    INTEGER NOT NULL DEFAULT (unixepoch())
);

INSERT INTO tool_calls_v3
    SELECT id, message_id, turn_sequence, tool_name, input_json,
           output_json, duration_ms, success, error_message, created_at
    FROM tool_calls;

DROP TABLE tool_calls;
ALTER TABLE tool_calls_v3 RENAME TO tool_calls;

CREATE INDEX idx_tool_calls_message
    ON tool_calls(message_id, turn_sequence);
