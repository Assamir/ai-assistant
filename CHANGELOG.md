# Changelog — Assystent

All notable changes to this project are documented here. The format is inspired by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Desktop packaging: `electron-builder` Windows (NSIS) uses `frontend/resources/icon.png` as the application icon (`frontend/package.json` → `build.icon`).
- Avatar UX: crossfade (~0.42s, ease-out) between VRM expression weights when the WebSocket `emotion` changes; richer scene lighting (`hemisphereLight` + dual pulsing fill/key `pointLight`s).
- **T8 / Player profile:** `POST /api/v1/player-profile/games/{game}/archive` — writes the current YAML slice for that game to SQLite `player_profile_archives` (`season`, `reason` ∈ `season_reset` | `manual` | `backup`); does **not** clear live `player_profile.yaml` (see PRD / api-plan). `GET /api/v1/player-profile/archives` lists rows (optional `game`, `limit`).
- **T8 / Player profile commands:** `PATCH /api/v1/player-profile/games/{game}` — optional `league` / `game_version` (pusty PATCH → 400); przy zmianie **niepustej** ligi odpowiedź zawiera `archive_recommended` i broadcast WS **`player_profile.league_changed`** (bez auto-archiwum). `POST /api/v1/player-profile/games/{game}/active-character` `{ "character" }` — 422 gdy postaci nie ma na liście.
- **T8 / Daily meta:** `POST /api/v1/daily-checks/run` `{ "game", "force" }` — inserts `daily_checks`, updates `last_meta_check` in profile YAML, optional DuckDuckGo `web_search` when MCP enabled; `GET /api/v1/daily-checks` lists history. **Persists** a Markdown note under `{content_root}/{memory.knowledge_dir}/daily_checks/` and sets DB `knowledge_file_path`; **re-ingests** that file into Chroma when `memory.enabled` and ingester is present. Background: `mcp.daily_check_on_startup` / `ASSY_MCP__DAILY_CHECK_ON_STARTUP`, `daily_check_interval_hours`. WS `daily_check.complete`.

### Changed

- Refactored emotion weight math into `frontend/src/emotionBlend.ts` (shared helpers for normalization and blending).
