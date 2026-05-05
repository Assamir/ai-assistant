# Assystent

Lokalny asystent podczas grania: backend **FastAPI** (LLM/STT/TTS/MCP, WebSocket, profil gracza) i klient **Electron + React + Vite** z awatarem **VRM**.

Szczegóły środowiska, modeli i pierwszego uruchomienia: **[docs/ENV_SETUP.md](docs/ENV_SETUP.md)**. Zmiany wersji: **[CHANGELOG.md](CHANGELOG.md)**. Plany i status: **[docs/plan/implementation_plan_part2.md](docs/plan/implementation_plan_part2.md)**.

## Szybki start (dev)

1. **Python:** venv, `pip install -r requirements.txt`, uruchom backend (np. `uvicorn` z modułem aplikacji zgodnie z repo).
2. **Frontend:** w katalogu `frontend`: `npm install`, `npm run dev` (Vite). Pełna instrukcja w `docs/ENV_SETUP.md` §7–8.

## Release (Windows)

- Artefakt instalatora: **`frontend/release/`** po buildzie NSIS.
- Polecenie (z `frontend`): `npm run electron:dist` — najpierw `vite build`, potem `electron-builder --win` (ikona: `frontend/resources/icon.png`, zob. `frontend/package.json` → `build.icon`).

**Polityka produktowa (skrót):**

- Dystrybucja poza zespołem: traktuj build jako **binaria + konfiguracja użytkownika** (`content_root`, `config/config.yaml`, dane w `data/`). Nie wpinaj sekretów do repozytorium.
- Opcjonalna ochrona zapisu konfiguracji: **`ASSYSTENT_CONFIG_PUT_TOKEN`** + nagłówek przy `PUT /api/v1/config` (opis w `docs/ENV_SETUP.md` §11.5).
- Użytkownik końcowy odpowiada za **LM Studio / modele**, GPU i zawartość profilu gry (`player_profile.yaml`).

## Konfiguracja przez ENV

Prefiks **`ASSY_*`** nadpisuje YAML (np. `ASSY_OBSERVER__AUTO_LEAGUE_HINT_ON_GAME_DETECTED`). Lista i zasady: `docs/ENV_SETUP.md` §11.2.

## Licencje

Zależności mają własne licencje; przy publicznym release dołącz weryfikację `LICENSES` zgodnie z checklistą w planie (T14).
