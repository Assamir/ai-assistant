-- Relaksacja turn_sequence (config może mieć max_tool_calls_per_turn > 5).

PRAGMA foreign_keys = OFF;

CREATE TABLE tool_calls__new (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id    INTEGER NOT NULL REFERENCES messages(id),
    turn_sequence INTEGER NOT NULL CHECK(turn_sequence BETWEEN 1 AND 64),
    tool_name     TEXT    NOT NULL,
    input_json    TEXT    NOT NULL,
    output_json   TEXT,
    duration_ms   INTEGER,
    success       BOOLEAN NOT NULL DEFAULT FALSE,
    error_message TEXT,
    created_at    INTEGER NOT NULL DEFAULT (unixepoch())
);

INSERT INTO tool_calls__new SELECT * FROM tool_calls;
DROP TABLE tool_calls;
ALTER TABLE tool_calls__new RENAME TO tool_calls;

CREATE INDEX idx_tool_calls_message
    ON tool_calls(message_id, turn_sequence);

PRAGMA foreign_keys = ON;
