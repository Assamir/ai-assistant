# Changelog — Assystent

All notable changes to this project are documented here. The format is inspired by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Desktop packaging: `electron-builder` Windows (NSIS) uses `frontend/resources/icon.png` as the application icon (`frontend/package.json` → `build.icon`).
- Avatar UX: crossfade (~0.42s, ease-out) between VRM expression weights when the WebSocket `emotion` changes; richer scene lighting (`hemisphereLight` + dual pulsing fill/key `pointLight`s).

### Changed

- Refactored emotion weight math into `frontend/src/emotionBlend.ts` (shared helpers for normalization and blending).
