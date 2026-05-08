# Third-Party Licenses — Assystent

This document lists open-source components used by Assystent and their licenses.

---

## Backend (Python)

| Package | License | Notes |
|---------|---------|-------|
| [FastAPI](https://github.com/tiangolo/fastapi) | MIT | Web framework |
| [Uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause | ASGI server |
| [Pydantic v2](https://github.com/pydantic/pydantic) | MIT | Config validation |
| [PyYAML](https://github.com/yaml/pyyaml) | MIT | YAML config loading |
| [aiosqlite](https://github.com/omnilib/aiosqlite) | MIT | Async SQLite |
| [httpx](https://github.com/encode/httpx) | BSD-3-Clause | HTTP client (LLM API) |
| [tiktoken](https://github.com/openai/tiktoken) | MIT | Prompt token counting |
| [numpy](https://github.com/numpy/numpy) | BSD-3-Clause | Audio/image arrays |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT | STT engine (CTranslate2) |
| [librosa](https://github.com/librosa/librosa) | ISC | Audio processing / TTS modulation |
| [soundfile](https://github.com/bastibe/python-soundfile) | BSD-3-Clause | WAV I/O |
| [Pillow](https://github.com/python-pillow/Pillow) | HPND | Image processing |
| [mss](https://github.com/BoboTiG/python-mss) | MIT | Screen capture |
| [watchdog](https://github.com/gorakhargosh/watchdog) | Apache-2.0 | File system watcher (hot-reload) |
| [structlog](https://github.com/hynek/structlog) | MIT | Structured logging |
| [asteval](https://github.com/newville/asteval) | MIT | MCP calculator sandbox |
| [chromadb](https://github.com/chroma-core/chroma) | Apache-2.0 | Semantic memory (vector DB) |
| [duckduckgo-search](https://github.com/deedy5/duckduckgo_search) | MIT | MCP web_search backend |
| [trafilatura](https://github.com/adbar/trafilatura) | Apache-2.0 | MCP web_scraper text extraction |
| [pynput](https://github.com/moses-palmer/pynput) | LGPL-3.0 | Backend PTT hotkey listener (optional) |
| [openWakeWord](https://github.com/dscripka/openWakeWord) | Apache-2.0 | Wakeword detection (optional) |
| [PyTorch](https://github.com/pytorch/pytorch) | BSD-style | VLM / STT GPU inference (optional) |
| [transformers](https://github.com/huggingface/transformers) | Apache-2.0 | Moondream2 VLM (optional) |
| [easyocr](https://github.com/JaidedAI/EasyOCR) | Apache-2.0 | OCR engine (optional) |
| [Playwright](https://github.com/microsoft/playwright-python) | Apache-2.0 | Web scraper SPA fallback (optional) |
| [py7zr](https://github.com/miurahr/py7zr) | LGPL-2.1 | Log archive compression (optional) |
| [pytest](https://github.com/pytest-dev/pytest) | MIT | Test framework |
| [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio) | Apache-2.0 | Async test support |

---

## Frontend (JavaScript / Electron)

| Package | License | Notes |
|---------|---------|-------|
| [Electron](https://github.com/electron/electron) | MIT | Desktop shell |
| [React](https://github.com/facebook/react) | MIT | UI framework |
| [Three.js](https://github.com/mrdoob/three.js) | MIT | 3D rendering |
| [@pixiv/three-vrm](https://github.com/pixiv/three-vrm) | MIT | VRM avatar loader |
| [@react-three/fiber](https://github.com/pmndrs/react-three-fiber) | MIT | React renderer for Three.js |
| [@react-three/drei](https://github.com/pmndrs/drei) | MIT | Three.js helpers |
| [Vite](https://github.com/vitejs/vite) | MIT | Frontend build tool |
| [electron-builder](https://github.com/electron-userland/electron-builder) | MIT | Packaging / NSIS installer |
| [cross-env](https://github.com/kentcdodds/cross-env) | MIT | Cross-platform env vars |

---

## AI Models

| Model | License | Source |
|-------|---------|--------|
| Gemma 4 E4B (default LLM) | [Gemma Terms of Use](https://ai.google.dev/gemma/terms) | via LM Studio |
| Faster-Whisper large-v3 | MIT (model weights: CC-BY-4.0) | OpenAI Whisper / SYSTRAN |
| Piper `pl_PL-gosia-medium` | CC0 | [Rhasspy/piper-voices](https://github.com/rhasspy/piper) |
| Moondream2 | Apache-2.0 | [vikhyatk/moondream2](https://huggingface.co/vikhyatk/moondream2) |

---

## Avatar (VRM)

The default VRM avatar model is sourced from [VRoid Hub](https://hub.vroid.com/) under a **CC-BY** license.
Attribution must be displayed in the application's Credits section and in this file once a specific model is selected.

> **TODO:** Replace this placeholder with the actual model name, author, and VRoid Hub URL once the final avatar is chosen.

---

## Piper TTS Binary

[Piper](https://github.com/rhasspy/piper) — MIT License.
Voice models distributed separately under their respective licenses (see model JSON sidecar files).

---

*Last updated: 2026-05-08*
