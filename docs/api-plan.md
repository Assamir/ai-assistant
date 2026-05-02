# REST API Plan — Assystent (Local AI Gaming Assistant)

> **Version:** 1.0
> **Date:** 2026-04-27
> **Stack:** Python 3.10+ / FastAPI, SQLite + ChromaDB, WebSocket, OpenAI-compatible LLM (LM Studio)
> **Base URL:** `http://127.0.0.1:8000` (localhost-only binding)
> **API Prefix:** `/api/v1`
> **Real-time channel:** `ws://127.0.0.1:8000/ws`

---

## 1. Resources

The API exposes resources mapped to database tables and PRD-driven business capabilities. Some resources are virtual (file-backed YAML/MD on disk) and exposed for management; others are pure runtime concerns (voice pipeline, observer loop).

| # | Resource | Backing | PRD reference |
|---|----------|---------|---------------|
| 1 | **Sessions** | `sessions` table | PRD_01 §6, PRD_04 §3.3 (Circuit Breaker) |
| 2 | **Messages** | `messages` table + `messages_fts` | PRD_02 §3 (LLM), §4 (Observer) |
| 3 | **Tool Calls** | `tool_calls` table | PRD_02 §5 (MCP Tools) |
| 4 | **Documents** | `generated_documents` + filesystem | PRD_02 §7 |
| 5 | **MCP Cache** | `mcp_cache` table | PRD_02 §5.2 |
| 6 | **MCP Tools** | runtime (web_search, web_scraper, etc.) | PRD_02 §5 |
| 7 | **Player Profile** | YAML + `player_context_snapshots` + `player_profile_archives` | PRD_02 §6.1 |
| 8 | **Game Profiles** | YAML files in `config/game_profiles/` | PRD_02 §4.2 |
| 9 | **Game Detections** | `game_detections` table | PRD_02 §4 (F-OB-10) |
| 10 | **Daily Checks** | `daily_checks` table | PRD_02 §6.2 |
| 11 | **Personas** | MD files in `personas/` | PRD_02 §3, PRD_05 §2 |
| 12 | **Knowledge Base** | ChromaDB `knowledge_base` + MD files in `knowledge/` | PRD_02 §6.2 |
| 13 | **Memory (Semantic)** | ChromaDB `conversations` | PRD_02 §6 (F-ME-02) |
| 14 | **Configuration** | `config.yaml` + `system_state` table | PRD_04 §6 |
| 15 | **Commands** | `commands.yaml` + regex matcher | PRD_02 §9 |
| 16 | **Observer** | runtime + `system_state` | PRD_02 §4 |
| 17 | **Voice Pipeline** | runtime (STT/LLM/TTS chain) | PRD_02 §2, §3 |
| 18 | **Audio Devices** | OS enumeration | PRD_02 F-VO-06/07 |
| 19 | **System / Health** | `health_events` + circuit breaker + `system_state` | PRD_03 §5.3, PRD_01 §6 |
| 20 | **Backups** | filesystem (`backups/`) | PRD_05 §7.3 |
| 21 | **Debug** | runtime ring-buffer | PRD_03 §5.2 |

---

## 2. Endpoints

### 2.1 Conventions

- **Content-Type:** `application/json` unless noted (audio uploads use `multipart/form-data`).
- **Timestamps in responses:** ISO 8601 (UTC), e.g. `"2026-04-27T14:32:01Z"`. Internal storage uses `unixepoch()`.
- **Pagination:** `?page=1&limit=50` (defaults). Max `limit=200`. Response always includes `pagination` envelope.
- **Filtering:** documented per endpoint.
- **Sorting:** `?sort=field` ascending, `?sort=-field` descending. Default per resource.
- **Streaming:** Server-Sent Events (`text/event-stream`) for token streams; WebSocket for audio.
- **Error envelope:**
  ```json
  {
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "Human-readable message",
      "details": { "field": "..." }
    }
  }
  ```
- **Standard error codes:** `400 VALIDATION_ERROR`, `404 NOT_FOUND`, `409 CONFLICT`, `422 UNPROCESSABLE`, `423 LOCKED` (e.g. degraded state), `429 RATE_LIMITED`, `503 SERVICE_UNAVAILABLE` (LLM down), `500 INTERNAL_ERROR`.

---

### 2.2 Sessions

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/sessions/current` | Get currently active session (the one with `ended_at IS NULL`) |
| GET | `/api/v1/sessions` | List sessions (paginated) |
| GET | `/api/v1/sessions/{id}` | Get a specific session including aggregated stats |
| POST | `/api/v1/sessions/{id}/end` | Force-end a session (admin / debug) |

**`GET /api/v1/sessions`**

Query params: `page`, `limit`, `sort` (default `-started_at`), `health_state`, `game` (filters by any detected game), `started_after`, `started_before`.

Response `200`:
```json
{
  "data": [
    {
      "id": 42,
      "started_at": "2026-04-27T08:15:33Z",
      "ended_at": "2026-04-27T11:42:18Z",
      "duration_seconds": 12405,
      "game_detected": "poe2",
      "health_state": "healthy",
      "stats": {
        "messages_total": 184,
        "messages_user": 23,
        "messages_assistant": 25,
        "messages_observer": 134,
        "tool_calls_total": 18,
        "documents_generated": 2
      }
    }
  ],
  "pagination": { "page": 1, "limit": 50, "total": 137 }
}
```

**`GET /api/v1/sessions/current`**

Response `200` if active session exists, `404 NOT_FOUND` otherwise.

**`POST /api/v1/sessions/{id}/end`**

No body. Sets `ended_at = unixepoch()`. Returns updated session. `409 CONFLICT` if already ended.

---

### 2.3 Messages (Conversation Log)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/messages` | List messages (paginated, filterable) |
| GET | `/api/v1/messages/{id}` | Get a single message with linked tool_calls |
| GET | `/api/v1/messages/search` | Full-text search using FTS5 |
| POST | `/api/v1/messages/{id}/forget` | Mark message archived + remove from semantic memory ("Zapomnij o X") |

**`GET /api/v1/messages`**

Query params:
- `session_id` (int)
- `source` (enum: `user`, `assistant`, `observer`, `system`; multi: `?source=user&source=assistant`)
- `archived` (bool, default `false`)
- `created_after`, `created_before` (ISO 8601)
- `emotion` (one of 16 emotions)
- `page`, `limit` (max 200), `sort` (default `-created_at`)

Response `200`:
```json
{
  "data": [
    {
      "id": 9182,
      "session_id": 42,
      "source": "assistant",
      "content": "Hmm, ten build wymaga lepszego łuku...",
      "emotion": "thinking",
      "confidence_score": null,
      "scene_hash": null,
      "include_in_semantic_memory": true,
      "chroma_embedding_id": "msg-9182",
      "archived": false,
      "created_at": "2026-04-27T10:14:22Z",
      "tool_calls_count": 1
    }
  ],
  "pagination": { "page": 1, "limit": 50, "total": 184 }
}
```

**`GET /api/v1/messages/search`** — FTS5 full-text

Query params:
- `q` (required, min length 2) — FTS5 query syntax
- `session_id`, `source`, `game` (filters)
- `limit` (max 100, default 25)

Response `200`:
```json
{
  "data": [
    {
      "id": 9182,
      "session_id": 42,
      "source": "assistant",
      "content": "Hmm, ten build wymaga lepszego łuku...",
      "rank": -8.142,
      "snippet": "...ten <mark>build</mark> wymaga..."
    }
  ],
  "query": "build łuk"
}
```

**`POST /api/v1/messages/{id}/forget`**

Sets `archived = TRUE`, `archived_at = unixepoch()`, deletes Chroma embedding if `chroma_embedding_id` set, nulls the reference. Returns `204 No Content`. `404` if not found.

---

### 2.4 Tool Calls

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/tool-calls` | List tool calls (paginated) |
| GET | `/api/v1/tool-calls/{id}` | Get specific tool call with full input/output JSON |
| GET | `/api/v1/messages/{message_id}/tool-calls` | List tool calls for a message |

**`GET /api/v1/tool-calls`**

Query params: `tool_name`, `success` (bool), `session_id`, `created_after`, `created_before`, `page`, `limit`.

Response `200`:
```json
{
  "data": [
    {
      "id": 512,
      "message_id": 9182,
      "turn_sequence": 1,
      "tool_name": "web_search",
      "input": { "query": "PoE2 Lightning Arrow build season 2" },
      "output_summary": "5 results returned",
      "duration_ms": 832,
      "success": true,
      "error_message": null,
      "created_at": "2026-04-27T10:14:18Z"
    }
  ],
  "pagination": { "page": 1, "limit": 50, "total": 18 }
}
```

`GET /api/v1/tool-calls/{id}` returns full `input_json` and `output_json` (no truncation).

---

### 2.5 Documents

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/documents` | List generated documents |
| GET | `/api/v1/documents/{id}` | Document metadata |
| GET | `/api/v1/documents/{id}/content` | Download/raw content (Content-Type per format) |
| POST | `/api/v1/documents` | Generate a new document on demand |
| DELETE | `/api/v1/documents/{id}` | Soft-delete (file removed via `deleted_files_log`) |
| POST | `/api/v1/documents/open-folder` | Open `documents/` folder in Windows Explorer ("Otwórz dokumenty") |

**`GET /api/v1/documents`**

Query params: `session_id`, `format` (`md` | `html`), `topic` (LIKE), `created_after`, `created_before`, `page`, `limit`, `sort` (default `-created_at`).

Response `200`:
```json
{
  "data": [
    {
      "id": 7,
      "session_id": 42,
      "tool_call_id": 512,
      "filename": "build_comparison_2026-04-27.html",
      "format": "html",
      "topic": "Lightning Arrow vs Tornado Shot",
      "file_path": "c:\\ai\\asystent\\documents\\build_comparison_2026-04-27.html",
      "file_exists": true,
      "file_size_bytes": 24812,
      "created_at": "2026-04-27T10:15:42Z"
    }
  ],
  "pagination": { "page": 1, "limit": 50, "total": 14 }
}
```

**`POST /api/v1/documents`**

Request body:
```json
{
  "topic": "Lightning Arrow vs Tornado Shot comparison",
  "format": "html",
  "instructions": "Compare clear speed, single target, gear cost. Include Mermaid diagrams.",
  "data_sources": ["web_search:results-id-123", "knowledge_base:poe2"]
}
```

Response `201 Created`:
```json
{
  "id": 7,
  "filename": "build_comparison_2026-04-27.html",
  "format": "html",
  "file_path": "c:\\ai\\asystent\\documents\\build_comparison_2026-04-27.html",
  "file_size_bytes": 24812,
  "preview_url": "/api/v1/documents/7/content",
  "created_at": "2026-04-27T10:15:42Z"
}
```

Validation: `format ∈ {md, html}`, `topic` required (1-200 chars), `instructions` (1-4000 chars).

**`GET /api/v1/documents/{id}/content`**

Returns raw file content with appropriate `Content-Type`:
- `md` → `text/markdown; charset=utf-8`
- `html` → `text/html; charset=utf-8`

`410 Gone` if `file_path IS NULL` (already physically deleted).

**`DELETE /api/v1/documents/{id}`**

Removes DB row; trigger `trg_document_delete` queues file in `deleted_files_log` for cleanup job. Returns `204`. Sandbox check: file_path must be inside content_root.

---

### 2.6 MCP Tools (Direct Invocation)

These endpoints are intended primarily for backend internal use (function-calling from LLM), but exposed via REST for testing, frontend manual invocation, and debugging. All tools enforce the **sandbox** (NF-S-04..06) and **rate limits** (PRD_02 §5.3).

| Method | Path | Description | Cache TTL |
|---|---|---|---|
| POST | `/api/v1/mcp/web-search` | DuckDuckGo / SearXNG search | 24h game meta / 1h general |
| POST | `/api/v1/mcp/web-scraper` | Fetch and parse URL | 7 days |
| GET | `/api/v1/mcp/time` | Current local time | none |
| POST | `/api/v1/mcp/calculator` | Safe expression eval (asteval) | none |
| POST | `/api/v1/mcp/screen-capture` | One-shot screen capture + VLM analysis | none |
| GET | `/api/v1/mcp/tools` | Discovery: list all tools with JSON schemas |

**`POST /api/v1/mcp/web-search`**

Request:
```json
{
  "query": "Path of Exile 2 best builds season 2",
  "max_results": 10,
  "category": "game_meta",
  "force_refresh": false
}
```

Response `200`:
```json
{
  "results": [
    { "title": "...", "url": "https://...", "snippet": "..." }
  ],
  "from_cache": true,
  "cache_age_seconds": 3210,
  "rate_limit": { "remaining": 7, "reset_in_seconds": 42 }
}
```

`429 RATE_LIMITED` after 10 req/min. `503 SERVICE_UNAVAILABLE` if offline.

**`POST /api/v1/mcp/web-scraper`**

Request:
```json
{
  "url": "https://maxroll.gg/poe2/build-guides/lightning-arrow",
  "force_refresh": false
}
```

Response `200`:
```json
{
  "url": "...",
  "title": "Lightning Arrow Deadeye",
  "content": "## Build Overview\n...",
  "content_format": "markdown",
  "from_cache": false,
  "fetched_at": "2026-04-27T10:11:02Z"
}
```

**`POST /api/v1/mcp/calculator`**

Request:
```json
{ "expression": "(245 * 1.35 + 80) * 0.92" }
```

Response `200`:
```json
{ "expression": "...", "result": 380.6364, "result_type": "float" }
```

`422 UNPROCESSABLE` for unsafe operations or syntax errors.

**`POST /api/v1/mcp/screen-capture`**

Request:
```json
{
  "include_cursor_crop": true,
  "cursor_crop_size": [600, 400],
  "vlm_prompt": "Describe what is shown on screen, focus on element near cursor",
  "include_ocr": true
}
```

Response `200`:
```json
{
  "vlm_description": "Player viewing inventory tooltip for a rare bow with...",
  "ocr_text": "Vaal Bow\nAdds 45-78 Lightning Damage\nTier 2 - Lightning",
  "cursor_position": [1247, 632],
  "captured_at": "2026-04-27T10:18:14Z",
  "screenshot_id": "tmp-abc123"
}
```

**`GET /api/v1/mcp/tools`**

Response `200`:
```json
{
  "tools": [
    {
      "name": "web_search",
      "description": "Search the web via DuckDuckGo",
      "schema": { /* JSON schema for OpenAI function calling */ },
      "rate_limit_per_minute": 10,
      "cache_ttl_seconds": 86400,
      "requires_internet": true
    }
  ]
}
```

---

### 2.7 MCP Cache (Admin)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/mcp/cache` | List cached entries (paginated) |
| GET | `/api/v1/mcp/cache/stats` | Aggregated stats per tool (count, hit_count avg, total size) |
| DELETE | `/api/v1/mcp/cache` | Clear all cache |
| DELETE | `/api/v1/mcp/cache/{tool_name}` | Clear cache for specific tool |
| DELETE | `/api/v1/mcp/cache/expired` | Run expiry cleanup |

`GET /api/v1/mcp/cache` query params: `tool_name`, `expired_only`, `page`, `limit`.

---

### 2.8 Player Profile

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/player-profile` | Full YAML profile as JSON |
| PUT | `/api/v1/player-profile` | Replace full profile (admin) |
| GET | `/api/v1/player-profile/games` | List games in profile |
| GET | `/api/v1/player-profile/games/{game}` | Game-specific section |
| PUT | `/api/v1/player-profile/games/{game}/active-character` | Switch active character ("Gram teraz X") |
| POST | `/api/v1/player-profile/games/{game}/characters` | Add new character |
| PUT | `/api/v1/player-profile/games/{game}/characters/{name}` | Update character |
| DELETE | `/api/v1/player-profile/games/{game}/characters/{name}` | Remove character |
| POST | `/api/v1/player-profile/games/{game}/import-build` | Import build from URL (uses web_scraper) |
| POST | `/api/v1/player-profile/games/{game}/archive` | Archive (season reset) |
| GET | `/api/v1/player-profile/snapshots` | Context snapshots history |
| GET | `/api/v1/player-profile/archives` | List archived profiles |
| GET | `/api/v1/player-profile/archives/{id}` | Get archived profile YAML |

**`GET /api/v1/player-profile`**

Response `200`:
```json
{
  "games": {
    "poe2": {
      "active_character": "SparkyBoy",
      "league": "Season 2",
      "characters": [
        {
          "name": "SparkyBoy",
          "class": "Deadeye",
          "build": "Lightning Arrow",
          "level": 87,
          "build_url": "https://maxroll.gg/poe2/...",
          "notes": "Potrzebuje lepszego łuku"
        }
      ],
      "last_meta_check": "2026-04-25"
    }
  },
  "updated_at": "2026-04-27T08:15:33Z"
}
```

**`PUT /api/v1/player-profile/games/{game}/active-character`**

Request: `{ "character_name": "TankMaster" }`. Validates character exists in game's character list.
Response `200` returns updated game section. Triggers a `player_context_snapshots` row with `trigger='character_change'`.

**`POST /api/v1/player-profile/games/{game}/import-build`**

Request:
```json
{
  "build_url": "https://maxroll.gg/poe2/build-guides/lightning-arrow",
  "character_name": "SparkyBoy"
}
```

Behaviour: backend invokes `web_scraper` → LLM extracts build data → updates character. If scraper fails (SPA / JS-required), responds `422` with `details.action: "ask_user"` so frontend prompts user to enter data manually.

Response `200`:
```json
{
  "character": { /* updated character */ },
  "extracted_fields": ["build", "build_url", "notes"],
  "source": "scraper"
}
```

**`POST /api/v1/player-profile/games/{game}/archive`**

Request:
```json
{
  "season": "Season 2",
  "reason": "season_reset"
}
```

Validation: `reason ∈ {season_reset, manual, backup}`. Saves YAML to `player_profile_archives`. The current profile section is **not** auto-cleared — frontend prompts the user (per PRD_02 §6.3 "Nigdy nie kasuje automatycznie"). Returns `archive_id`.

---

### 2.9 Game Profiles (configuration)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/game-profiles` | List available game profiles (YAML files) |
| GET | `/api/v1/game-profiles/{game}` | Get specific profile |
| POST | `/api/v1/game-profiles/reload` | Hot-reload all profiles from disk |

Game profiles are file-driven (per PRD_02 §4.2). The API is read-only — users edit YAML files directly. Hot-reload is triggered automatically by file watcher; this endpoint forces it.

**`GET /api/v1/game-profiles/{game}`** Response `200`:
```json
{
  "name": "Path of Exile 2",
  "process_names": ["PathOfExile_x64.exe", "PathOfExileSteam.exe"],
  "observer_type": "action",
  "observer_interval_seconds": 5,
  "focus_areas": ["builds", "loot", "combat", "boss_mechanics"],
  "screen_regions": [
    { "name": "health_mana", "position": "bottom-left", "size": "15%" }
  ],
  "context_prompt": "Jesteś ekspertem od PoE2...",
  "mcp_sources": ["poe2 wiki", "maxroll.gg/poe2"],
  "loaded_from": "config/game_profiles/poe2.yaml",
  "loaded_at": "2026-04-27T08:15:33Z"
}
```

---

### 2.10 Game Detections

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/game-detections` | History of game detections |
| GET | `/api/v1/game-detections/current` | Currently detected game (if any) |
| POST | `/api/v1/game-detections/manual-override` | Manually set game ("ręczne nadpisanie" — F-OB-10) |
| DELETE | `/api/v1/game-detections/manual-override` | Clear manual override → resume auto-detect |

**`POST /api/v1/game-detections/manual-override`**

Request: `{ "game": "poe2" }`. Validates game profile exists. Returns `200` with current detection. Internally creates a `game_detections` row with `detection_method='manual'`.

---

### 2.11 Daily Checks

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/daily-checks` | List daily check runs |
| GET | `/api/v1/daily-checks/latest` | Latest check per game (one row per game) |
| POST | `/api/v1/daily-checks/run` | Trigger a meta check now (background task) |
| POST | `/api/v1/daily-checks/{id}/mark-notified` | Mark `user_notified=true` |

**`POST /api/v1/daily-checks/run`**

Request: `{ "game": "poe2", "force_refresh": true }`. Returns `202 Accepted` with `task_id`. Status broadcast over WebSocket `daily_check.complete` event.

---

### 2.12 Personas

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/personas` | List personas (filenames in `personas/`) |
| GET | `/api/v1/personas/{name}` | Get persona content (raw .md) |
| GET | `/api/v1/personas/active` | Currently active persona |
| PUT | `/api/v1/personas/active` | Switch active persona ("Zmień personę na X") |
| POST | `/api/v1/personas/reload` | Force reload from disk |

Personas are user-edited .md files. API does **not** offer create/update/delete (NF-Q-05 hot-reload). Active persona stored in `system_state.current_persona`.

**`PUT /api/v1/personas/active`**

Request: `{ "name": "komentator" }`. Validates file `personas/komentator.md` exists. Returns active persona summary. Hot-reloads system prompt builder.

---

### 2.13 Knowledge Base

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/knowledge` | List ingested files (grouped by source_file) |
| POST | `/api/v1/knowledge/ingest` | Ingest a file from `knowledge/` into ChromaDB |
| POST | `/api/v1/knowledge/reindex` | Re-ingest all files |
| DELETE | `/api/v1/knowledge/{source_file}` | Remove all chunks for a file |
| POST | `/api/v1/knowledge/search` | Direct semantic search over knowledge base |

**`POST /api/v1/knowledge/ingest`**

Request:
```json
{
  "file_path": "knowledge/poe2/season2_meta.md",
  "game": "poe2",
  "type": "manual"
}
```

Validation: `file_path` must be inside `knowledge/` (sandbox). `type ∈ {daily_check, manual, wiki}`. Returns chunk count.

**`POST /api/v1/knowledge/search`**

Request:
```json
{
  "query": "Lightning Arrow gem links",
  "game": "poe2",
  "k": 5
}
```

Response:
```json
{
  "results": [
    {
      "text": "...",
      "score": 0.87,
      "source_file": "poe2/season2_meta.md",
      "section_title": "Lightning Arrow",
      "chunk_index": 3
    }
  ]
}
```

---

### 2.14 Memory (Semantic Recall)

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/memory/search` | Semantic recall over conversations + knowledge |
| GET | `/api/v1/memory/stats` | ChromaDB collection sizes, last rotation |
| POST | `/api/v1/memory/rotate` | Force FIFO rotation if over limit |

**`POST /api/v1/memory/search`**

Request:
```json
{
  "query": "What did I say about my Deadeye build?",
  "scope": ["conversations", "knowledge"],
  "k_conversations": 3,
  "k_knowledge": 2,
  "filters": {
    "game": "poe2",
    "source": ["user", "assistant"]
  }
}
```

Response `200`:
```json
{
  "conversations": [
    {
      "message_id": 8044,
      "content": "...",
      "score": 0.91,
      "session_id": 41,
      "created_at": "2026-04-26T19:22:11Z",
      "metadata": { "game": "poe2", "emotion": "amused" }
    }
  ],
  "knowledge": [
    {
      "text": "...",
      "score": 0.84,
      "source_file": "poe2/season2_meta.md",
      "section_title": "Deadeye Builds"
    }
  ]
}
```

**`GET /api/v1/memory/stats`** Response:
```json
{
  "conversations": { "count": 9842, "limit": 10000, "fill_pct": 98.4 },
  "knowledge_base": { "count": 1284, "limit": null },
  "last_rotation_at": "2026-04-26T22:01:00Z"
}
```

---

### 2.15 Observer (Game Loop)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/observer` | Current observer state |
| POST | `/api/v1/observer/start` | Start observer loop ("Zacznij obserwować") |
| POST | `/api/v1/observer/stop` | Stop observer loop |
| PUT | `/api/v1/observer/interval` | Change interval ("Ustaw interwał na N sekund") |
| POST | `/api/v1/observer/screen-query` | One-shot screen analysis ("Co widzisz na ekranie?") |

**`GET /api/v1/observer`**

Response:
```json
{
  "state": "running",
  "current_game": "poe2",
  "interval_seconds": 5,
  "last_capture_at": "2026-04-27T10:18:14Z",
  "scenes_analyzed_this_session": 134,
  "ambient_enabled": false
}
```

`state ∈ {idle, running, paused}`. Paused = paused due to `Conversation Lock` per PRD_01 §5.2.

**`POST /api/v1/observer/start`**

Request (optional): `{ "interval_seconds": 5, "game_override": "poe2" }`.
Response `200` returns new state. `409 CONFLICT` if already running. `503` if no game detected and no override.

**`PUT /api/v1/observer/interval`**

Request: `{ "interval_seconds": 10 }`. Validation: `5 ≤ value ≤ 300`.

**`POST /api/v1/observer/screen-query`**

Request:
```json
{
  "question": "Co widzisz na ekranie?",
  "include_cursor_context": true,
  "voice_response": true
}
```

`voice_response: true` → result is also synthesized via TTS and broadcast on WebSocket.
Response `200`:
```json
{
  "vlm_description": "...",
  "ocr_text": "...",
  "answer": "Patrzysz na tooltip rzadkiego łuku z affixami...",
  "answer_emotion": "amused",
  "captured_at": "2026-04-27T10:18:14Z"
}
```

---

### 2.16 Voice Pipeline

The full pipeline (PTT) runs over WebSocket for streaming, but REST endpoints are exposed for synchronous use, debugging, and component-level testing.

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/voice/transcribe` | STT only — audio → text |
| POST | `/api/v1/voice/synthesize` | TTS only — text → audio |
| POST | `/api/v1/voice/chat` | LLM chat (text in / text+emotion out, optional streaming) |
| POST | `/api/v1/voice/process` | Full pipeline — audio → text → LLM → audio |

**`POST /api/v1/voice/transcribe`**

Request: `multipart/form-data`
- `audio`: file (WAV/PCM 16kHz mono preferred)
- `language` (optional): `pl` | `en` | `auto` (default `auto`)

Response `200`:
```json
{
  "text": "Jakie są najlepsze buildy w PoE2?",
  "language": "pl",
  "confidence": 0.92,
  "duration_ms": 412,
  "action_hint": "process"
}
```

`action_hint`:
- `process` (confidence > 0.7) — high confidence
- `confirm` (0.4 ≤ confidence ≤ 0.7) — frontend should confirm before sending to LLM
- `reject` (confidence < 0.4) — frontend should ask user to repeat

Per PRD_02 §2.1.

**`POST /api/v1/voice/synthesize`**

Request:
```json
{
  "text": "Witaj! Jak mogę pomóc?",
  "emotion": "happy",
  "voice_id": "pl_PL_male_default",
  "format": "wav"
}
```

Validation: `emotion ∈ {neutral, happy, amused, ..., sarcastic}` (16 values + neutral). `text` 1-2000 chars. `format ∈ {wav, mp3}`.

Response `200`: binary audio with appropriate Content-Type.

**`POST /api/v1/voice/chat`** (text-only, supports SSE streaming)

Request:
```json
{
  "text": "Co sądzisz o tym buildzie?",
  "stream": true,
  "include_tools": true,
  "context_override": null
}
```

Non-streaming response `200`:
```json
{
  "message_id": 9183,
  "content": "Hmm, ten build wymaga lepszego łuku...",
  "emotion": "thinking",
  "tool_calls": [
    { "id": 513, "tool_name": "web_search", "duration_ms": 832 }
  ],
  "duration_ms": 1842,
  "language_used": "pl"
}
```

Streaming response (`Accept: text/event-stream`):
```
event: token
data: {"text": "Hmm, "}

event: token
data: {"text": "ten "}

event: tool_call
data: {"tool_name": "web_search", "input": {...}}

event: emotion
data: {"emotion": "thinking"}

event: done
data: {"message_id": 9183, "duration_ms": 1842}
```

**`POST /api/v1/voice/process`** — Full PTT pipeline

Request: `multipart/form-data` with `audio` field + optional `metadata` JSON field. Returns the assistant audio as binary stream + headers `X-Message-Id`, `X-Emotion`, `X-Duration-Ms`. For streaming use WebSocket instead (preferred for low latency, F-AI-05).

Errors:
- `423 LOCKED` — system in `degraded` state (LM Studio down) — body contains text-only fallback
- `429 RATE_LIMITED` — too many requests
- `503 SERVICE_UNAVAILABLE` — STT/TTS module unavailable

---

### 2.17 Audio Devices

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/audio/devices` | List input + output devices |
| GET | `/api/v1/audio/devices/current` | Currently selected devices |
| PUT | `/api/v1/audio/devices/input` | Set input device (mic) |
| PUT | `/api/v1/audio/devices/output` | Set output device |

**`GET /api/v1/audio/devices`**

Response:
```json
{
  "input": [
    { "id": "default", "name": "Default", "is_default": true },
    { "id": "wasapi:1234", "name": "Headset Microphone", "is_default": false }
  ],
  "output": [ /* ... */ ]
}
```

---

### 2.18 Audio Mode (PTT / Wakeword / Silent)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/audio/mode` | Current input mode |
| PUT | `/api/v1/audio/mode` | Switch PTT ↔ wakeword (F-VO-03) |
| GET | `/api/v1/audio/silent` | Silent mode state |
| PUT | `/api/v1/audio/silent` | Toggle silent mode ("Wycisz się"/"Możesz mówić") |
| PUT | `/api/v1/audio/volume` | TTS volume |

**`PUT /api/v1/audio/mode`**

Request: `{ "mode": "wakeword", "wakeword": "Hej Asystent" }`. Validation: `mode ∈ {ptt, wakeword}`.

---

### 2.19 Configuration

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/config` | Full effective config |
| GET | `/api/v1/config/{section}` | Section (`general`, `audio`, `observer`, `ai`, `models`, `storage`, `documents`, `mcp`, `debug`, `persona`) |
| PATCH | `/api/v1/config/{section}` | Patch config section |
| POST | `/api/v1/config/reload` | Force reload `config.yaml` from disk |
| GET | `/api/v1/config/schema` | JSON Schema for config validation |

**`PATCH /api/v1/config/general`**

Request: `{ "language": "en", "proactivity_level": "active" }`. Validation: language ∈ {pl, en}; proactivity_level ∈ {passive, moderate, active}; quiet_hours = pair of HH:MM strings.

Response `200` returns updated section. Persists to `config.yaml`. Some changes require restart (per NF-Q hot-reload table) — response includes `restart_required: true` field.

---

### 2.20 System State (Runtime Key-Value)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/state` | All system_state keys |
| GET | `/api/v1/state/{key}` | Single key |
| PUT | `/api/v1/state/{key}` | Update key (validated) |
| POST | `/api/v1/state/proactivity` | Set proactivity level |

Allowed keys (per `system_state` table seed): `circuit_breaker_state`, `audio_mode`, `silent_mode`, `proactivity_level`, `observer_interval_seconds`, `current_persona`, `active_session_id`, `last_chroma_rotation`. Keys are whitelisted; arbitrary keys rejected with `400`.

---

### 2.21 Commands (System Commands)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/commands` | List all built-in + custom commands (regex patterns) |
| POST | `/api/v1/commands/match` | Test text against command matcher (returns matched command or null) |
| POST | `/api/v1/commands/execute` | Execute named command directly (bypasses STT/LLM) |
| POST | `/api/v1/commands/reload` | Reload `commands.yaml` |

**`POST /api/v1/commands/execute`**

Request:
```json
{
  "name": "set_observer_interval",
  "params": { "interval": 15 }
}
```

Response: `{ "executed": true, "result": { /* per-command */ } }`. `404` if command name unknown. `422` if params invalid.

---

### 2.22 Health & System Status

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/status` | Comprehensive system status |
| GET | `/api/v1/health` | Lightweight liveness probe |
| GET | `/api/v1/health/ready` | Readiness — components reachable |
| GET | `/api/v1/health/circuit-breaker` | Circuit breaker detail |
| POST | `/api/v1/health/circuit-breaker/reset` | Force reset breaker to CLOSED |
| GET | `/api/v1/health/events` | Health event log (paginated, filterable) |

**`GET /api/v1/status`**

Response `200`:
```json
{
  "health_state": "healthy",
  "session_id": 42,
  "components": {
    "lm_studio": { "status": "up", "url": "http://localhost:1234/v1", "latency_ms": 14 },
    "stt": { "status": "up", "model": "faster-whisper-medium" },
    "tts": { "status": "up", "engine": "piper" },
    "vlm": { "status": "up", "model": "moondream2" },
    "ocr": { "status": "up", "engine": "easyocr" },
    "internet": { "status": "up", "checked_at": "..." }
  },
  "resources": {
    "vram_used_mb": 2840,
    "ram_used_mb": 1420,
    "cpu_percent": 4.2
  },
  "observer": { "state": "running", "current_game": "poe2" },
  "circuit_breaker": { "state": "CLOSED", "failures": 0 },
  "uptime_seconds": 12405,
  "version": "1.0.0"
}
```

**`GET /api/v1/health`** (lightweight)

Response `200`: `{ "status": "ok", "uptime_seconds": 12405 }` — used by SessionWatchdog and frontend heartbeat.

**`GET /api/v1/health/events`**

Query params: `component`, `event_type`, `since` (ISO 8601), `page`, `limit`.

---

### 2.23 Backups

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/backups` | List backups in `backups/` |
| POST | `/api/v1/backups` | Create backup ("Zrób backup") |
| GET | `/api/v1/backups/{filename}/download` | Download backup zip |
| DELETE | `/api/v1/backups/{filename}` | Remove backup file |

**`POST /api/v1/backups`**

Request (optional): `{ "include_logs": true, "include_screenshots": false }`.
Response `202 Accepted`:
```json
{
  "task_id": "bkp-abc123",
  "filename": "assystent_backup_2026-04-27.zip"
}
```

Long-running task — completion broadcast on WebSocket as `backup.complete`.

---

### 2.24 Debug

Available only when `debug.enabled: true` in config.

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/debug/last-interaction` | Full pipeline of last interaction |
| GET | `/api/v1/debug/screenshots` | List captured screenshots (when save_screenshots=true) |
| GET | `/api/v1/debug/screenshots/{filename}` | Download specific screenshot |
| GET | `/api/v1/debug/pipeline-log` | Recent pipeline events |

`GET /api/v1/debug/last-interaction` response:
```json
{
  "captured_at": "2026-04-27T10:14:22Z",
  "audio_meta": { "duration_ms": 2104, "sample_rate": 16000 },
  "stt": { "text": "...", "confidence": 0.92, "duration_ms": 412 },
  "command_match": null,
  "prompt": { "system": "...", "user": "...", "context_tokens": 1842 },
  "llm": { "response": "...", "ttft_ms": 312, "total_ms": 1480, "tool_calls": [...] },
  "emotion_parsed": "thinking",
  "tts": { "duration_ms": 502, "tts_params": { "speed": 0.85, "pitch": -2 } }
}
```

When `debug.enabled: false`: all `/debug/*` return `404 NOT_FOUND`.

---

### 2.25 Sandbox / Files

Restricted operations on content root only (NF-S-04..06).

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/files/open-folder` | Open a folder in Explorer (e.g., `documents/`) |
| GET | `/api/v1/files/content-root` | Returns configured content root path |

**`POST /api/v1/files/open-folder`**

Request: `{ "folder": "documents" }`. Whitelist: `documents`, `logs`, `backups`, `knowledge`, `personas`, `data`. Any other path → `403 FORBIDDEN`.

---

### 2.26 WebSocket Channel

`ws://127.0.0.1:8000/ws`

Single WebSocket multiplexing all real-time events. Per PRD_04 §7.1.

**Heartbeat:** server pings every 5s; frontend must respond `pong` within 15s or connection drops. Auto-reconnect from frontend with state sync via `GET /api/v1/status`.

#### Server → Frontend events

| Event | Payload | Description |
|---|---|---|
| `audio_stream` | binary frames | TTS PCM audio (chunked, for lip-sync) |
| `audio_stream_start` | `{ message_id, sample_rate, format }` | Start of audio stream |
| `audio_stream_end` | `{ message_id, duration_ms }` | End marker |
| `emotion` | `{ emotion, intensity }` | Emotion change (16 emotions) |
| `status` | `{ state, health, current_game }` | State machine update (idle/listening/thinking/speaking/sleep) |
| `text_overlay` | `{ text, message_id }` | Used in silent mode |
| `config_update` | `{ section, changed_keys }` | Hot-reload notification |
| `observer_event` | `{ scene_description, message_id }` | Observer comment generated |
| `daily_check.complete` | `{ game, has_changes, summary }` | Daily check result |
| `backup.complete` | `{ task_id, filename, success }` | Backup finished |
| `error` | `{ code, message }` | Recoverable error notification |
| `transcript_low_confidence` | `{ text, confidence }` | STT requests confirmation |

#### Frontend → Server events

| Event | Payload | Description |
|---|---|---|
| `ptt_start` | `{}` | User pressed PTT — start recording |
| `audio_chunk` | binary frame | Mic audio chunk |
| `ptt_end` | `{}` | Released PTT — process buffer |
| `wakeword_detected` | `{ phrase }` | Frontend-side wakeword triggered |
| `text_input` | `{ text, stream: true }` | Text input bypassing STT |
| `confirm_transcription` | `{ text, confirmed }` | Response to low-confidence prompt |
| `interrupt` | `{}` | Stop current TTS playback (audio duck on PTT) |
| `pong` | `{}` | Heartbeat reply |

---

## 3. Authentication and Authorization

### 3.1 Threat model

This is a **single-user local desktop application** with a Python/FastAPI backend talking to a paired Electron frontend. No multi-tenant access. Per PRD_01 §3 ("Produkt do użytku osobistego") and NF-S-01 ("zero transmisji do chmury"), the API does not need user accounts.

### 3.2 Network binding

The FastAPI server **MUST** bind exclusively to `127.0.0.1` (localhost). Binding to `0.0.0.0` is forbidden and rejected at startup. This is the primary access control: any process on the local machine can talk to the API, but no remote machine can.

### 3.3 Origin / CSRF

For browser-context attacks (a malicious local web page calling localhost), the API:
- Sets `Access-Control-Allow-Origin` to the Electron app origin only (`file://` or `http://localhost:<port>`).
- Validates `Origin` header on state-changing methods (POST/PUT/PATCH/DELETE) — `403 FORBIDDEN` if mismatched.
- WebSocket performs the same `Origin` check during handshake.

### 3.4 Token (optional hardening)

A single shared secret token may be generated at first run and stored in `config/auth.token` (file-mode 0600 equivalent on Windows). The Electron app reads it locally and includes it as `X-Auth-Token` header / `?token=` query for WebSocket. This is an extra layer for users who run untrusted local code, **not** required by the threat model.

### 3.5 Authorization

All endpoints are equally accessible — no roles. The single user is implicitly an admin. **Sandbox (NF-S-04..06)** is enforced not by authorization but by the file-path validator (whitelist against content root) inside MCP tools and document/file endpoints.

### 3.6 Rate limiting

Per-tool rate limits enforced server-side (PRD_02 §5.3):
- `web_search`: 10 req/min (sliding window)
- Other MCP tools: no limit

Implemented in middleware/MCP layer; `429` returned with `Retry-After` header when exceeded.

---

## 4. Validation and Business Logic

### 4.1 Validation Rules per Resource

#### Sessions
- `health_state ∈ {healthy, degraded, minimal, crashed, resumed_after_hibernate}` (DB CHECK).
- Only one active session at a time (`ended_at IS NULL`); enforced via `idx_sessions_active` unique condition + startup cleanup.
- Cannot end an already-ended session → `409 CONFLICT`.

#### Messages
- `source ∈ {user, assistant, observer, system}` (DB CHECK).
- `content` length > 0 (DB CHECK).
- `emotion ∈` {16 PRD emotions} ∪ {null}.
- `confidence_score ∈ [0.0, 1.0]` if not null.
- `scene_hash`: only for `source = 'observer'`; expected length 64 (SHA256).
- `archived` and `archived_at` consistency: setting `archived=true` must set `archived_at`.

#### Tool Calls
- `turn_sequence ∈ [1, 5]` (DB CHECK; ties to `max_tool_calls_per_turn`).
- `tool_name ∈ {web_search, web_scraper, get_current_time, calculator, generate_document, screen_capture}`.
- `input_json` must be valid JSON conforming to tool's schema.
- `success=true` requires `error_message` to be null and `output_json` to be present.

#### Documents
- `format ∈ {md, html}` (DB CHECK).
- `filename` must be unique within `documents/` directory (suffix with timestamp if collision).
- `file_path` must be inside content root (sandbox). Resolution is canonicalized and validated.
- `topic` 1-200 chars; `instructions` 1-4000 chars on creation request.

#### MCP Cache
- `cache_key` length = 64 (DB CHECK; SHA256 hex).
- `ttl_seconds > 0` (DB CHECK).
- Cache-key generation: `SHA256(tool_name + canonical_json(params))` (DB §Decisions #4).
- Expired entries (`created_at + ttl_seconds < unixepoch()`) excluded from reads.

#### Player Profile
- Game must have a corresponding profile in `config/game_profiles/` to be added.
- `active_character` must reference an existing character within the same game.
- Character `name` must be unique within a game.
- `level ∈ [1, 100]`, `class` from a configurable enum per game profile.
- `build_url` must be a valid URL.

#### Player Profile Snapshots
- `trigger ∈ {session_start, character_change, game_detected}` (DB CHECK).
- Auto-created — no direct API write; emitted by orchestrator.

#### Player Profile Archives
- `reason ∈ {season_reset, manual, backup}` (DB CHECK).
- `season` non-empty when `reason = 'season_reset'`.

#### Game Profiles (file)
- Filename matches `^[a-z0-9_]+\.yaml$`.
- Required keys: `name`, `process_names` (non-empty array), `observer_type`, `observer_interval_seconds`.
- `observer_interval_seconds ∈ [5, 300]`.

#### Game Detections
- `detection_method ∈ {process, vlm, manual}` (DB CHECK).
- `game` must match an existing game profile.

#### Daily Checks
- `game` must reference a game profile.
- `has_changes` and `result_summary` consistency: if `has_changes=true`, `result_summary` non-empty.

#### Personas (file)
- Filename matches `^[a-z0-9_-]+\.md$`.
- Active persona must exist in `personas/`; setting non-existent name → `404`.

#### Knowledge Base
- `source_file` path must be inside `knowledge/` (sandbox).
- `type ∈ {daily_check, manual, wiki}`.
- Re-ingesting a file deletes prior chunks first (via `where={"source_file": ...}`).

#### Configuration
- Each section validated against JSON Schema (exposed at `/api/v1/config/schema`).
- `language ∈ {pl, en}`.
- `proactivity_level ∈ {passive, moderate, active}`.
- `quiet_hours`: array of two HH:MM strings.
- `audio.stt_confidence_threshold ∈ [0.0, 1.0]`, `stt_low_confidence_threshold ≤ stt_confidence_threshold`.
- `observer.default_interval_seconds ∈ [5, 300]`.
- `mcp.web_search_rate_limit ∈ [1, 60]`.
- `models.tts ∈ {piper, xttsv2}`, `models.vlm ∈ {moondream2, llava}`.
- `storage.backend ∈ {sqlite, postgres, gcp_firestore}`.
- `storage.archive_days ≥ 7`.
- `storage.semantic_memory_limit ≥ 100`.
- `documents.default_format ∈ {md, html}`, `html_theme ∈ {dark, light}`.
- `persona.active` must reference a file in `personas/`.

#### Voice Pipeline
- Audio: 16-bit PCM mono, 8/16/22.05/44.1/48 kHz; max 60 s per request.
- `language ∈ {pl, en, auto}` for transcribe.
- `emotion ∈` {16 emotions, neutral} for synthesize.
- `text` 1-2000 chars for synthesize; 1-8000 for chat.
- Confidence thresholds (PRD_02 §2.1):
  - `> 0.7` → `process`
  - `[0.4, 0.7]` → `confirm`
  - `< 0.4` → `reject`

### 4.2 Business Logic Mapping (PRD → Endpoint)

| PRD Capability | Endpoint(s) | Notes |
|---|---|---|
| **Voice PTT pipeline** (F-VO-01, US-01) | `POST /voice/process` + WebSocket `ptt_start/audio_chunk/ptt_end` | Streaming preferred over WebSocket |
| **Wakeword mode** (F-VO-02, F-VO-03) | `PUT /audio/mode` + WebSocket `wakeword_detected` | Frontend handles detection (lighter VRAM) |
| **STT confidence handling** (F-VO-04, §2.1) | `POST /voice/transcribe` returns `action_hint`; frontend confirms via `confirm_transcription` event | |
| **TTS with emotion modulation** (F-VO-05, §6.4) | `POST /voice/synthesize` accepts `emotion` param | Speed/pitch table applied server-side |
| **Audio duck on PTT** (F-VO-08) | WebSocket `interrupt` event from frontend | <200ms target |
| **Silent mode / text overlay** (F-VO-10) | `PUT /audio/silent` + WebSocket `text_overlay` | |
| **LLM streaming** (F-AI-05) | `POST /voice/chat` with SSE | TTFT < 0.5s target |
| **Inline emotion tags** (F-AI-07) | Backend parses `[EMO:tag]` from response, broadcasts `emotion` event, strips before TTS | |
| **Persona switching** (F-AI-04, US-06) | `PUT /personas/active` | Hot-reloads system prompt |
| **Function calling / tool use** (F-AI-06) | LLM internally calls MCP endpoints via FastAPI in-process; also exposed via `/mcp/*` for testing | `max_tool_calls_per_turn=5` |
| **Game observer loop** (F-OB-01..05, US-02/03) | `POST /observer/start`, `PUT /observer/interval`, `POST /observer/stop` | Server-driven; events on WebSocket |
| **On-demand screen query** (F-OB-08, US-04) | `POST /observer/screen-query` or `POST /mcp/screen-capture` | Cursor crop optional |
| **Cascade game detection** (F-OB-10) | Background task; results in `game_detections`; manual override via `POST /game-detections/manual-override` | |
| **Web search MCP** (PRD_02 §5) | `POST /mcp/web-search` | Rate limited 10/min |
| **Web scraper MCP** | `POST /mcp/web-scraper` | TTL 7d |
| **Calculator MCP** | `POST /mcp/calculator` | asteval safe-eval |
| **Time MCP** | `GET /mcp/time` | No cache |
| **Document generation** (F-DOC-01..06, US-05) | `POST /documents` | Two-layer response: voice summary + file |
| **Open documents folder** (cmd) | `POST /files/open-folder` with `documents` | Sandbox enforced |
| **Player profile multi-character** (F-ME-03, US-02) | `PUT /player-profile/games/{game}/active-character` | Triggers snapshot |
| **Build import from URL** (PRD_02 §6.1) | `POST /player-profile/games/{game}/import-build` | Uses scraper; falls back to manual |
| **Daily meta check** (PRD_02 §6.2) | Auto on startup if `daily_check_on_startup=true`; manual via `POST /daily-checks/run` | |
| **Season reset** (PRD_02 §6.3) | `POST /player-profile/games/{game}/archive` after user confirmation | Never auto-deletes |
| **Conversation history** (F-ME-01) | `GET /messages?session_id=X` | Repository pattern |
| **Semantic recall** (F-ME-02) | `POST /memory/search` | ChromaDB conversations + knowledge |
| **Auto-archive >90 days** (F-ME-05) | Background scheduler (no API trigger needed) | `archived` flag set; logs compressed |
| **FIFO rotation** (F-ME-06) | `POST /memory/rotate` (forced); auto when `count >= 10000` | |
| **Forget command** (F-ME-07) | `POST /messages/{id}/forget` | Removes embedding + archives row |
| **Backup** (US-via cmd) | `POST /backups` | Zips content root |
| **System commands without LLM** (PRD_02 §9) | Match before LLM; `POST /commands/match` for testing; `POST /commands/execute` for direct invocation | Regex with named groups |
| **Status / health** (NF-Q, PRD_03 §5.3) | `GET /status`, `GET /health/*` | Includes circuit breaker |
| **Circuit breaker recovery** (PRD_01 §6) | Internal state machine; visible via `GET /health/circuit-breaker`; reset via POST | 3 failures → OPEN; 30s → HALF_OPEN |
| **Hibernation recovery** (PRD_01 §6 SessionWatchdog) | WebSocket emits `status` events on reconnect; frontend re-syncs via `GET /status` | |
| **Quiet hours / proactivity** (PRD_05 §3) | `PATCH /config/general` ; `POST /state/proactivity` | Server checks before broadcasting observer events |
| **Hot-reload config/personas** (NF-Q-05) | Auto via file watcher; manual via `POST /config/reload`, `POST /personas/reload`, `POST /game-profiles/reload`, `POST /commands/reload` | Broadcasts `config_update` |
| **Sandbox** (NF-S-04..06) | Path validator middleware on file/document/knowledge endpoints | Whitelist `c:\ai\asystent\**` |
| **Debug pipeline** (PRD_03 §5.2) | `GET /debug/last-interaction`; gated by `config.debug.enabled` | |

### 4.3 Cross-cutting Logic

#### Health-state aware degradation

When `system_state.circuit_breaker_state = OPEN` (LM Studio down), endpoints that require LLM return `423 LOCKED`:
```json
{
  "error": {
    "code": "DEGRADED_STATE",
    "message": "Nie mogę teraz myśleć, LM Studio wyłączone",
    "details": { "health_state": "degraded", "retry_after_seconds": 30 }
  }
}
```

Affected endpoints: `/voice/chat`, `/voice/process`, `/observer/start`, `/observer/screen-query` (LLM step), `/documents` (POST), `/daily-checks/run`. STT/TTS-only and read-only endpoints continue to work.

#### Conversation-lock on PTT

When PTT is active (`audio_mode` recording), the observer loop pauses automatically. `GET /observer` returns `state: "paused"`. After PTT release + LLM response complete, observer resumes.

#### Streaming TTS for low TTFT

`POST /voice/chat` with `stream: true` emits SSE tokens. The orchestrator simultaneously feeds the token stream to TTS, which produces audio chunks pushed over WebSocket — meeting NF-P-01 end-to-end < 3s.

#### Two-layer document responses

`POST /documents` (or LLM-invoked `generate_document` tool) returns the document file metadata, but the orchestrator additionally synthesizes a **voice summary** that is sent to TTS — fulfilling F-DOC-06 ("dwuwarstwowa odpowiedź: głos + plik").

#### Memory hygiene

- After every assistant or user message with `include_in_semantic_memory=true`, an embedding is added to ChromaDB and `chroma_embedding_id` stored.
- Periodic FIFO rotation (`POST /memory/rotate` or auto when `count >= 10000`) deletes oldest from Chroma and nulls `chroma_embedding_id` in SQLite.
- `POST /messages/{id}/forget` removes from both stores atomically.

#### Sandbox enforcement

A central `validate_path(path: Path) -> Path` utility:
1. Resolves to canonical absolute path.
2. Checks the resolved path is a descendant of `config.general.content_root`.
3. Rejects symlinks pointing outside the root.
4. Used by every endpoint that accepts user-supplied paths.

Violations return `403 FORBIDDEN` with `code: SANDBOX_VIOLATION`.

#### Idempotency

POST endpoints that create resources (`POST /documents`, `POST /backups`, `POST /daily-checks/run`) accept an optional `Idempotency-Key` header. Repeated calls within 5 minutes with the same key return the original result instead of creating a duplicate.

#### Pagination envelope

All list endpoints return:
```json
{
  "data": [ /* ... */ ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 137,
    "has_more": true
  }
}
```

#### Time normalization

DB stores `unixepoch()` (seconds). API responses convert to ISO 8601 UTC. API requests accept either (epoch int or ISO string) — auto-detected.

#### WebSocket reconnect protocol

1. Client connects to `/ws`.
2. Server sends `welcome` event with `session_id`, `current_state`, `last_message_id`.
3. Client may then call `GET /api/v1/messages?session_id=X&id_gt=last_message_id` to backfill missed messages.
4. Server resumes broadcasting events.

#### Observer event flow

1. Observer loop captures screen → VLM analyzes → produces `scene_hash`.
2. Hash compared with previous scene hash; identical → skip (deduplication, F-OB-07).
3. Otherwise → LLM generates comment with emotion → message inserted (`source='observer'`) → TTS → broadcast `observer_event` + `audio_stream` + `emotion`.
4. Notification sound played (if `audio.notification_sound=true`) before TTS.

#### Daily meta check flow

1. On startup, scheduler checks `daily_checks` for each active game; if `MAX(checked_at) < now - 24h`, queue background task.
2. Task uses `web_search` MCP → produces `result_summary` + writes `knowledge_file_path`.
3. Result inserted into `daily_checks`. If `has_changes=true`, broadcast `daily_check.complete` over WebSocket.
4. Frontend / orchestrator may proactively notify user (subject to `proactivity_level` and quiet hours) — once notified, `POST /daily-checks/{id}/mark-notified` flips the flag.
