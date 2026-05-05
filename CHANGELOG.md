# Changelog — Assystent

All notable changes to this project are documented here. The format is inspired by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **T8 / Auto league hint:** `observer.auto_league_hint_on_game_detected` (YAML) lub `ASSY_OBSERVER__AUTO_LEAGUE_HINT_ON_GAME_DETECTED` — po `game_detected` z znanym `game_id` uruchamia `check-league-hint`; przy `mismatch_hint` broadcast WS `player_profile.league_hint` (jak REST `broadcast: true`). Dokumentacja ENV: `docs/ENV_SETUP.md` §11.2.
- **Frontend:** baner + badge „Liga” (karta Połączenie) dla WS `player_profile.league_hint` oraz `player_profile.league_changed`.
- Desktop packaging: `electron-builder` Windows (NSIS) uses `frontend/resources/icon.png` as the application icon (`frontend/package.json` → `build.icon`).
- **README:** skrócona instrukcja dev/release + polityka dystrybucji (`README.md`).
- Avatar UX: crossfade (~0.42s, ease-out) between VRM expression weights when the WebSocket `emotion` changes; richer scene lighting (`hemisphereLight` + dual pulsing fill/key `pointLight`s).
- **T8 / Player profile:** `POST /api/v1/player-profile/games/{game}/archive` — writes the current YAML slice for that game to SQLite `player_profile_archives` (`season`, `reason` ∈ `season_reset` | `manual` | `backup`); does **not** clear live `player_profile.yaml` (see PRD / api-plan). `GET /api/v1/player-profile/archives` lists rows (optional `game`, `limit`).
- **T8 / League hint:** `POST /api/v1/player-profile/games/{game}/check-league-hint` `{ "broadcast"?: bool }` — `web_search` (gdy MCP), heurystyka: czy tekst z wyników zawiera **zapisaną** `league` profilu; `mismatch_hint` / `archive_suggested` (bez auto-zapisu). Opcjonalny WS **`player_profile.league_hint`** gdy `broadcast: true` i rozbieżność.
- **T8 / Player profile commands:** `PATCH /api/v1/player-profile/games/{game}` — optional `league` / `game_version` (pusty PATCH → 400); przy zmianie **niepustej** ligi odpowiedź zawiera `archive_recommended` i broadcast WS **`player_profile.league_changed`** (bez auto-archiwum). `POST /api/v1/player-profile/games/{game}/active-character` `{ "character" }` — 422 gdy postaci nie ma na liście.
- **T8 / Daily meta:** `POST /api/v1/daily-checks/run` `{ "game", "force" }` — inserts `daily_checks`, updates `last_meta_check` in profile YAML, optional DuckDuckGo `web_search` when MCP enabled; `GET /api/v1/daily-checks` lists history. **Persists** a Markdown note under `{content_root}/{memory.knowledge_dir}/daily_checks/` and sets DB `knowledge_file_path`; **re-ingests** that file into Chroma when `memory.enabled` and ingester is present. Background: `mcp.daily_check_on_startup` / `ASSY_MCP__DAILY_CHECK_ON_STARTUP`, `daily_check_interval_hours`. WS `daily_check.complete`.

### Changed

- Avatar: jawna mapa wszystkich emocji z `emotions.json` na rodziny palet w `AuraLights` (fallback rodziny: neutral); exponential kołysanie tułowia w idle i lerp barw świateł bez zmiany logiki crossfade ekspresji.
- Refactored emotion weight math into `frontend/src/emotionBlend.ts` (shared helpers for normalization and blending).
